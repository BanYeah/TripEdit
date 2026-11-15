"""Cumulative constraints for the eight turns of scenario 004."""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from database import connect

ARRIVAL = datetime(2026, 11, 2, 9)
DEPARTURE = datetime(2026, 11, 4, 15)

STATION = 20174971
HOTEL = 1672210391
HAENYEO = 1316561754
SHINBALWON = 8407645
SUBYEON = {14635779, 769611948, 596548360}
GALBI = 8149130
JAEGI = 16213715
TTOSIA = 147026116
SECOND_DAY = ARRIVAL.date() + timedelta(days=1)


def _start(segment):
    return datetime.fromisoformat(segment["start_time"])


def _end(segment):
    return datetime.fromisoformat(segment["end_time"])


def _visits(context, place_ids):
    return [stop for stop in context["stops"] if stop["place_id"] in place_ids]


def _opening_intervals(place, day):
    weekday = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[day.weekday()]
    intervals = json.loads(place["opening_hours"])[weekday]
    result = []
    midnight = datetime.combine(day, datetime.min.time())
    for opening, closing in intervals:
        def at(value):
            hours, minutes = map(int, value.split(":"))
            return midnight + timedelta(hours=hours, minutes=minutes)
        start, end = at(opening), at(closing)
        if end <= start:
            end += timedelta(days=1)
        result.append((start, end))
    return result


def validate_request_status(context):
    expected = "completed"
    if context["request_status"] != expected:
        return False, f"Request must be marked {expected}."
    return True, ""


def validate_trip_dates(context):
    itinerary = context["itinerary"]
    if _start(itinerary) != ARRIVAL or _end(itinerary) != DEPARTURE:
        return False, "Trip must run from Nov 2 09:00 to Nov 4 15:00."
    for segment in context["segments"]:
        if not ARRIVAL <= _start(segment) < _end(segment) <= DEPARTURE:
            return False, "Segments must stay within the trip dates."
    return True, ""


def validate_arrival(context):
    stops = context["stops"]
    if not stops or stops[0]["place_id"] != STATION or _start(stops[0]) != ARRIVAL:
        return False, "Trip must start at Sinhaeundae Station on Nov 2 at 09:00."
    minutes = int(context["places"][STATION]["arrival_after"])
    if _end(stops[0]) < ARRIVAL + timedelta(minutes=minutes):
        return False, f"Allow at least {minutes} minutes after arrival at Sinhaeundae Station."
    return True, ""


def validate_departure(context):
    stops = context["stops"]
    if not stops or stops[-1]["place_id"] != STATION or _end(stops[-1]) != DEPARTURE:
        return False, "Trip must end at Sinhaeundae Station on Nov 4 at 15:00."
    minutes = int(context["places"][STATION]["departure_before"])
    if _start(stops[-1]) > DEPARTURE - timedelta(minutes=minutes):
        return False, f"Allow at least {minutes} minutes before departure at Sinhaeundae Station."
    return True, ""


def validate_accommodation(context):
    hotels = _visits(context, {HOTEL})
    if not hotels:
        return False, "Stay at Ananti Cove."
    if any(
        context["places"][stop["place_id"]]["category"] == "accommodation"
        and stop["place_id"] != HOTEL
        for stop in context["stops"]
    ):
        return False, "All accommodation stays must be at Ananti Cove."

    # From turn 2 the first hotel visit is luggage storage, not check-in.
    stays = hotels[1:] if context["turn_num"] >= 2 else hotels
    if not stays:
        return False, "Return to Ananti Cove for check-in after leaving luggage."
    place = context["places"][HOTEL]
    midnight = datetime.combine(ARRIVAL.date(), datetime.min.time())

    def at(value):
        hours, minutes = map(int, value.split(":"))
        return midnight + timedelta(hours=hours, minutes=minutes)

    opening, closing = map(at, place["check-in"].split("-"))
    if closing <= opening:
        closing += timedelta(days=1)
    if not opening <= _start(stays[0]) <= closing:
        return False, "Check in at Ananti Cove within the Nov 2 check-in window."
    checkout = at(place["check-out"]) + (DEPARTURE.date() - ARRIVAL.date())
    if _end(stays[-1]) > checkout:
        return False, "Leave Ananti Cove by check-out time on Nov 4."

    for offset in (1, 2):
        start = midnight + timedelta(days=offset)
        end = start + timedelta(hours=6)
        covered = start
        for stop in stays:
            if _start(stop) <= covered < _end(stop):
                covered = _end(stop)
        if covered < end:
            return False, f"Stay at Ananti Cove throughout {start.date()} 00:00-06:00."
    return True, ""


def validate_requested_places(context):
    turn = context["turn_num"]
    groups = []
    if turn >= 2:
        groups.append({HAENYEO})
    if turn >= 3:
        groups.append({SHINBALWON})
    if 4 <= turn < 7:
        groups.append(SUBYEON)
    if turn >= 5:
        groups.append({GALBI})
    if turn >= 6:
        groups.append({JAEGI})
    if turn >= 8:
        groups.append({TTOSIA})
    allowed = {STATION, HOTEL}
    for group in groups:
        allowed |= group
        if len(_visits(context, group)) != 1:
            names = ", ".join(context["places"][key]["name"] for key in sorted(group))
            return False, f"Schedule exactly one visit to: {names}."
    if turn >= 7 and _visits(context, SUBYEON):
        return False, "Remove all Subyeon Choego Pork Soup visits after cancellation."
    if any(stop["place_id"] not in allowed for stop in context["stops"]):
        return False, "Do not add unrequested places."
    return True, ""


def validate_minimum_durations(context):
    for stop in context["stops"]:
        place = context["places"][stop["place_id"]]
        if "min_duration" in place:
            minutes = int(place["min_duration"])
            if _end(stop) - _start(stop) < timedelta(minutes=minutes):
                return False, f"Visit to {place['name']} must last at least {minutes} minutes."
    return True, ""


def validate_opening_hours(context):
    for stop in context["stops"]:
        place = context["places"][stop["place_id"]]
        if "opening_hours" not in place:
            continue
        start, end = _start(stop), _end(stop)
        intervals = _opening_intervals(place, start.date())
        intervals += _opening_intervals(place, start.date() - timedelta(days=1))
        if not any(opening <= start < end <= closing for opening, closing in intervals):
            return False, f"Visit to {place['name']} must be within opening hours."
    return True, ""


def validate_segment_times(context):
    segments = context["segments"]
    if any(_end(previous) > _start(current) for previous, current in zip(segments, segments[1:])):
        return False, "Segments must not overlap."
    return True, ""


def validate_meal_periods(context):
    meals = set()
    for stop in context["stops"]:
        if context["places"][stop["place_id"]]["category"] != "restaurant":
            continue
        start, end = _start(stop), _end(stop)
        midnight = datetime.combine(start.date(), datetime.min.time())
        if midnight + timedelta(hours=11) <= start < end <= midnight + timedelta(hours=15):
            period = "lunch"
        elif midnight + timedelta(hours=17) <= start < end <= midnight + timedelta(hours=21):
            period = "dinner"
        else:
            return False, "Restaurant visits must fit a lunch or dinner period."
        key = (start.date(), period)
        if key in meals:
            return False, "Schedule at most one restaurant per meal period."
        meals.add(key)
    return True, ""


def validate_luggage_then_lunch(context):
    stops = context["stops"]
    if len(stops) < 3 or [stop["place_id"] for stop in stops[:3]] != [STATION, HOTEL, HAENYEO]:
        return False, "Go directly from Sinhaeundae Station to Ananti Cove for luggage storage, then Songjeong Haenyeojip."
    if _end(stops[1]) - _start(stops[1]) != timedelta(minutes=10):
        return False, "Allow the requested 10 minutes for luggage storage at Ananti Cove."
    lunch = stops[2]
    midnight = datetime.combine(ARRIVAL.date(), datetime.min.time())
    if not midnight + timedelta(hours=11) <= _start(lunch) < _end(lunch) <= midnight + timedelta(hours=15):
        return False, "Visit Songjeong Haenyeojip for lunch on Nov 2."
    return True, ""


def validate_subyeon_on_tuesday(context):
    # Cancellation in turn 7 supersedes the earlier visit request.
    if context["turn_num"] >= 7:
        return True, ""
    stop = _visits(context, SUBYEON)[0]
    if _start(stop).date() != SECOND_DAY:
        return False, "Visit Subyeon Choego Pork Soup on Nov 3."
    return True, ""


def validate_galbi_reservation(context):
    stop = _visits(context, {GALBI})[0]
    if _start(stop) != datetime(2026, 11, 3, 19):
        return False, "Visit Haeundae Amso Galbijip for the Nov 3 19:00 reservation."
    return True, ""


# All turns are feasible. Turn 8 may move Jaegi to Tuesday lunch and
# Shinbalwon to Wednesday lunch, freeing Monday dinner for Ttosia.
TURN_CONSTRAINTS = {
    1: (
        validate_request_status,
        validate_trip_dates,
        validate_segment_times,
        validate_arrival,
        validate_departure,
        validate_accommodation,
        validate_requested_places,
        validate_minimum_durations,
        validate_opening_hours,
        validate_meal_periods,
    ),
    2: (validate_luggage_then_lunch,),
    3: (),  # Shinbalwon's date is not fixed by the user.
    4: (validate_subyeon_on_tuesday,),
    5: (validate_galbi_reservation,),
    6: (),  # Jaegi's date is not fixed by the user.
    7: (),  # Cancellation is checked by validate_requested_places.
    8: (),  # Ttosia is required; rearranging accepted visits is allowed.
}


def validator(turn_num, itinerary_id, request_status):
    if turn_num not in TURN_CONSTRAINTS:
        raise ValueError(f"Unsupported turn: {turn_num}")
    database = connect()
    try:
        itinerary = database.execute(
            "SELECT * FROM itineraries WHERE itinerary_id = ?", (itinerary_id,),
        ).fetchone()
        if itinerary is None:
            return False, "Itinerary not found."
        segments = [dict(row) for row in database.execute(
            "SELECT * FROM segments WHERE itinerary_id = ? ORDER BY start_time, segment_id",
            (itinerary_id,),
        ).fetchall()]
    finally:
        database.close()

    places = {}
    dataset_dir = Path(__file__).resolve().parents[2] / "dataset"
    for category in ("transport", "accommodation", "restaurant", "cafe", "attraction"):
        with (dataset_dir / f"{category}.csv").open(encoding="utf-8-sig", newline="") as file:
            places.update({int(row["place_id"]): row for row in csv.DictReader(file)})
    stops = [segment for segment in segments if segment["segment_type"] == "STOP"]
    if any(stop["place_id"] not in places for stop in stops):
        return False, "Itinerary contains an unknown place."
    context = {
        "itinerary": dict(itinerary), "segments": segments, "stops": stops,
        "places": places, "turn_num": turn_num, "request_status": request_status,
    }
    for turn in range(1, turn_num + 1):
        for constraint in TURN_CONSTRAINTS[turn]:
            success, reason = constraint(context)
            if not success:
                return success, reason
    return True, ""
