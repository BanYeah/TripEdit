"""Shared TripEdit benchmark rules for 101--110.

Use together with the repository's benchmark.validators.validate(), which checks
STOP/LEG alternation and travel times. This module validates the *scenario*
constraints and important itinerary invariants; it does not call a language model.
"""
from __future__ import annotations

import csv
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta
from functools import lru_cache
import json
from pathlib import Path

# Cache the last checked itinerary within one evaluator process. The official
# evaluate.py invokes validators in turn order, once per scenario/itinerary.
_PREVIOUS = {}
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_CATEGORIES = ("transport", "accommodation", "restaurant", "cafe", "attraction")


def dt(value):
    return datetime.fromisoformat(value)


def start(segment):
    return dt(segment["start_time"])


def end(segment):
    return dt(segment["end_time"])


@lru_cache(maxsize=1)
def read_places():
    directory = Path(__file__).resolve().parents[2] / "dataset"
    by_id, by_name = {}, {}
    for category in _CATEGORIES:
        with (directory / (category + ".csv")).open(encoding="utf-8-sig", newline="") as stream:
            for record in csv.DictReader(stream):
                key = int(record["place_id"])
                if key in by_id:
                    raise ValueError("Duplicate place_id: %s" % key)
                by_id[key] = record
                by_name.setdefault(record["name"], []).append(key)
    return by_id, by_name


def place_id(name):
    _, names = read_places()
    ids = names.get(name, [])
    if len(ids) != 1:
        raise ValueError("Name must identify exactly one place: %r (found %d)" % (name, len(ids)))
    return ids[0]


def opening_intervals(place, day):
    data = json.loads(place["opening_hours"])
    intervals = []
    midnight = datetime.combine(day, datetime.min.time())
    for lo, hi in data[_WEEKDAYS[day.weekday()]]:
        def convert(hhmm):
            h, m = (int(x) for x in hhmm.split(":"))
            return midnight + timedelta(hours=h, minutes=m)
        a, b = convert(lo), convert(hi)
        if b <= a:
            b += timedelta(days=1)
        intervals.append((a, b))
    return intervals


def is_open(place, begin, finish):
    if "opening_hours" not in place:
        return True
    times = opening_intervals(place, begin.date())
    times += opening_intervals(place, begin.date() - timedelta(days=1))
    return any(lo <= begin < finish <= hi for lo, hi in times)


def _match(active, name, day):
    matches = [i for i, v in enumerate(active) if v["place"] == name and v["day"] == day]
    if len(matches) != 1:
        raise ValueError("Cannot match unique visit %r, day=%d; got %d" % (name, day, len(matches)))
    return matches[0]


def build_active(spec, turn_num):
    """Replay add/replace/move/remove instructions; rejected requests do not apply."""
    active = []
    for turn_index, operations in enumerate(spec["turns"], 1):
        if turn_index > turn_num:
            break
        for item in operations:
            op = item["op"]
            if op == "reject":
                continue
            if op == "add":
                active.append(deepcopy({k: v for k, v in item.items() if k != "op"}))
            elif op == "replace":
                idx = _match(active, item["old"], item["day"])
                old = active[idx]
                new = deepcopy(old)
                new["place"] = item["place"]
                for key in ("at", "duration", "after", "before", "meal", "until"):
                    if key in item:
                        new[key] = item[key]
                active[idx] = new
                # Orders referring to an earlier meal should follow its replacement.
                for v in active:
                    if v.get("after") == item["old"] and v["day"] == item["day"]:
                        v["after"] = item["place"]
                    if v.get("before") == item["old"] and v["day"] == item["day"]:
                        v["before"] = item["place"]
            elif op == "move":
                active[_match(active, item["place"], item["day"])]["at"] = item["at"]
            elif op == "remove":
                del active[_match(active, item["place"], item["day"])]
            else:
                raise ValueError("Unknown operation: %s" % op)
    return active


def expected_status(spec, turn_num):
    return "unable_to_complete" if any(op["op"] == "reject" for op in spec["turns"][turn_num - 1]) else "completed"


def _ok():
    return True, ""


def _fail(message):
    return False, message


def _signature(itinerary, segments):
    fields = ("segment_type", "start_time", "end_time", "place_id", "place_name",
              "place_category", "transport_mode")
    return (itinerary["start_time"], itinerary["end_time"],
            tuple(tuple(s.get(f) for f in fields) for s in segments))


def _cover(stops, hotel_id, lo, hi):
    covered = lo
    for stop in sorted((s for s in stops if s["place_id"] == hotel_id), key=start):
        if start(stop) <= covered < end(stop):
            covered = max(covered, end(stop))
        if covered >= hi:
            return True
    return False


def _check_base(spec, itinerary, segments, stops, places, active):
    travel_start, travel_end = dt(spec["start"]), dt(spec["end"])
    if start(itinerary) != travel_start or end(itinerary) != travel_end:
        return _fail("Trip start/end do not match the requested times.")
    if not segments or not stops:
        return _fail("Itinerary has no segments/stops.")
    for i, s in enumerate(segments):
        if not travel_start <= start(s) < end(s) <= travel_end:
            return _fail("A segment is outside the trip or has invalid duration.")
        if i and start(s) < end(segments[i - 1]):
            return _fail("Segments overlap in time.")
        if s["segment_type"] not in ("STOP", "LEG"):
            return _fail("Unknown segment type.")
        if s["segment_type"] == "STOP" and int(s["place_id"]) not in places:
            return _fail("Unknown place_id.")
    if segments[0]["segment_type"] != "STOP" or segments[-1]["segment_type"] != "STOP":
        return _fail("A trip must start/end with a STOP.")
    if any(s["segment_type"] != ("STOP" if i % 2 == 0 else "LEG") for i, s in enumerate(segments)):
        return _fail("STOP and LEG must alternate.")

    origin, destination, hotel = (place_id(spec[k]) for k in ("origin", "destination", "hotel"))
    if stops[0]["place_id"] != origin or start(stops[0]) != travel_start:
        return _fail("Trip must start at the requested transport place/time.")
    if end(stops[0]) < travel_start + timedelta(minutes=int(places[origin]["arrival_after"])):
        return _fail("Insufficient arrival buffer at the first transport stop.")
    if stops[-1]["place_id"] != destination or end(stops[-1]) != travel_end:
        return _fail("Trip must end at the requested transport place/time.")
    if start(stops[-1]) > travel_end - timedelta(minutes=int(places[destination]["departure_before"])):
        return _fail("Insufficient departure buffer at the last transport stop.")

    # The requested places are exhaustive; AI cannot silently invent attractions/restaurants.
    expected = Counter((place_id(v["place"]), (travel_start + timedelta(days=v["day"] - 1)).date()) for v in active)
    observed = Counter()
    for i, s in enumerate(stops):
        pid = int(s["place_id"])
        category = places[pid]["category"]
        if category == "transport":
            if i not in (0, len(stops) - 1):
                return _fail("Unrequested intermediate transport stop.")
        elif category == "accommodation":
            if pid != hotel:
                return _fail("Only the specified hotel is allowed.")
        else:
            observed[(pid, start(s).date())] += 1
    if observed != expected:
        missing = expected - observed
        unexpected = observed - expected
        return _fail("Wrong scheduled visits (missing=%s, unexpected=%s)." % (dict(missing), dict(unexpected)))

    # Overnight coverage for each night; an itinerary may have gaps in daytime.
    day = travel_start.date() + timedelta(days=1)
    while day <= travel_end.date():
        lo = datetime.combine(day, datetime.min.time())
        hi = lo + timedelta(hours=6)
        if lo < travel_end and not _cover(stops, hotel, lo, hi):
            return _fail("Hotel must cover every overnight 00:00-06:00 period (%s)." % day)
        day += timedelta(days=1)

    meal_counts = Counter()
    explicit_durations = {(place_id(v["place"]), (travel_start + timedelta(days=v["day"] - 1)).date()): v.get("duration") for v in active}
    for s in stops:
        pid = int(s["place_id"])
        row = places[pid]
        a, b = start(s), end(s)
        if "min_duration" in row:
            explicit = explicit_durations.get((pid, a.date()))
            minimum = int(explicit if explicit is not None else row["min_duration"])
            if b - a < timedelta(minutes=minimum):
                return _fail("Too short a visit: %s (required >= %d min)." % (row["name"], minimum))
        if not is_open(row, a, b):
            return _fail("Outside opening hours: %s." % row["name"])
        if row["category"] == "restaurant":
            midnight = datetime.combine(a.date(), datetime.min.time())
            if midnight + timedelta(hours=11) <= a < b <= midnight + timedelta(hours=15):
                meal = "lunch"
            elif midnight + timedelta(hours=17) <= a < b <= midnight + timedelta(hours=21):
                meal = "dinner"
            else:
                return _fail("Restaurant is outside 11-15 lunch / 17-21 dinner hours.")
            key = (a.date(), meal)
            meal_counts[key] += 1
            if meal_counts[key] > 1:
                return _fail("More than one restaurant in a meal period.")
    return _ok()


def _check_visits(spec, stops, active):
    beginning = dt(spec["start"])
    by_key = {(int(s["place_id"]), start(s).date()): s
              for s in stops if s["segment_type"] == "STOP"}
    for visit in active:
        day = (beginning + timedelta(days=visit["day"] - 1)).date()
        this = by_key[(place_id(visit["place"]), day)]
        if visit.get("at"):
            when = datetime.combine(day, datetime.strptime(visit["at"], "%H:%M").time())
            if start(this) != when:
                return _fail("Wrong start time for %s: expected %s." % (visit["place"], when))
        if visit.get("until"):
            required_end = datetime.combine(day, datetime.strptime(visit["until"], "%H:%M").time())
            if end(this) != required_end:
                return _fail("Wrong end time for %s: expected %s." % (visit["place"], required_end))
        if visit.get("after"):
            anchor = by_key.get((place_id(visit["after"]), day))
            if anchor is None or start(this) < end(anchor):
                return _fail("%s must be after %s." % (visit["place"], visit["after"]))
        if visit.get("before"):
            anchor = by_key.get((place_id(visit["before"]), day))
            if anchor is None or end(this) > start(anchor):
                return _fail("%s must be before %s." % (visit["place"], visit["before"]))
        if visit.get("meal"):
            a, b = start(this), end(this)
            lunch = a.hour >= 11 and b <= datetime.combine(day, datetime.min.time()) + timedelta(hours=15)
            dinner = a.hour >= 17 and b <= datetime.combine(day, datetime.min.time()) + timedelta(hours=21)
            if not (lunch if visit["meal"] == "lunch" else dinner):
                return _fail("Wrong meal period for %s." % visit["place"])
    return _ok()


def validate_scenario(scenario_num, spec, turn_num, itinerary_id, request_status):
    """Interface expected by benchmark.validators.validate()."""
    if not (1 <= turn_num <= len(spec["turns"])):
        raise ValueError("Unsupported turn %s for scenario %s" % (turn_num, scenario_num))

    # Import inside function so static data checks can run without database.py.
    from database import connect

    connection = connect()
    try:
        itinerary = connection.execute("SELECT * FROM itineraries WHERE itinerary_id = ?", (itinerary_id,)).fetchone()
        if itinerary is None:
            return _fail("Itinerary not found.")
        itinerary = dict(itinerary)
        segments = [dict(r) for r in connection.execute(
            "SELECT * FROM segments WHERE itinerary_id = ? ORDER BY start_time, segment_id", (itinerary_id,)
        ).fetchall()]
    finally:
        connection.close()
    stops = [s for s in segments if s["segment_type"] == "STOP"]
    places, _ = read_places()
    active = build_active(spec, turn_num)
    actual = _signature(itinerary, segments)
    key = (scenario_num, itinerary_id)

    expected = expected_status(spec, turn_num)
    if request_status != expected:
        return _fail("Turn %d requires request_status.%s, got %s." % (turn_num, expected, request_status))
    if expected == "unable_to_complete":
        previous = _PREVIOUS.get(key)
        if previous is None or previous[0] != turn_num - 1:
            return _fail("Cannot verify rejected turn without previous turn's itinerary snapshot.")
        if actual != previous[1]:
            return _fail("The itinerary was modified during an impossible request.")
    result = _check_base(spec, itinerary, segments, stops, places, active)
    if result[0]:
        result = _check_visits(spec, stops, active)
    if result[0]:
        _PREVIOUS[key] = (turn_num, actual)
    return result
