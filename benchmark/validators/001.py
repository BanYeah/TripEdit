"""Cumulative constraints for the four turns of scenario 001."""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from database import connect

ARRIVAL = datetime(2026, 11, 16, 11)
DEPARTURE = datetime(2026, 11, 18, 20)

STATION = 8329752
TERMINAL = 26437842

SECOND_DAY = ARRIVAL.date() + timedelta(days=1)
HOTEL = 7862727
PIZZA = {10070964, 663545767}
TONSHOW = {1901662463, 590377149, 704518356}
VILLAGE = 22875776
CAFE = 568865089


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
    if context["request_status"] != "completed":
        return False, "Request must be marked completed."
    return True, ""


def validate_trip_dates(context):
    itinerary = context["itinerary"]
    if _start(itinerary) != ARRIVAL or _end(itinerary) != DEPARTURE:
        return False, "Trip must run from Nov 16 11:00 to Nov 18 20:00."
    for segment in context["segments"]:
        if not ARRIVAL <= _start(segment) < _end(segment) <= DEPARTURE:
            return False, "Segments must stay within the trip dates."
    return True, ""


def validate_arrival(context):
    stops = context["stops"]
    if not stops or stops[0]["place_id"] != STATION or _start(stops[0]) != ARRIVAL:
        return False, "Trip must start at Busan Station on Nov 16 at 11:00."
    minutes = int(context["places"][STATION]["arrival_after"])
    if _end(stops[0]) < ARRIVAL + timedelta(minutes=minutes):
        return False, f"Allow at least {minutes} minutes after arrival at Busan Station."
    return True, ""


def validate_departure(context):
    stops = context["stops"]
    if not stops or stops[-1]["place_id"] != TERMINAL or _end(stops[-1]) != DEPARTURE:
        return False, "Trip must end at Busan Port International Passenger Terminal on Nov 18 at 20:00."
    minutes = int(context["places"][TERMINAL]["departure_before"])
    if _start(stops[-1]) > DEPARTURE - timedelta(minutes=minutes):
        return False, f"Allow at least {minutes} minutes before departure at the terminal."
    return True, ""


def validate_accommodation(context):
    hotels = _visits(context, {HOTEL})
    if any(
        context["places"][stop["place_id"]]["category"] == "accommodation"
        and stop["place_id"] != HOTEL
        for stop in context["stops"]
    ):
        return False, "All accommodation stays must be at Lotte Hotel Busan."
    for day in (17, 18):
        start = datetime(2026, 11, day)
        end = start + timedelta(hours=6)
        # Permit adjacent hotel segments to jointly cover the overnight period.
        covered = start
        for stop in hotels:
            if _start(stop) <= covered < _end(stop):
                covered = _end(stop)
        if covered < end:
            return False, f"Stay at Lotte Hotel Busan throughout Nov {day} 00:00-06:00."
    return True, ""


def validate_requested_places(context):
    allowed = {STATION, TERMINAL, HOTEL}
    if context["turn_num"] >= 2:
        allowed |= PIZZA
    if context["turn_num"] >= 3:
        allowed |= TONSHOW
    if context["turn_num"] >= 4:
        allowed |= {VILLAGE, CAFE}
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


def validate_meal_periods(context):
    meals = set()
    for stop in context["stops"]:
        place = context["places"][stop["place_id"]]
        if place["category"] != "restaurant":
            continue
        start, end = _start(stop), _end(stop)
        # The explicit pizza opening-run request overrides the default lunch start.
        if stop["place_id"] in PIZZA and context["turn_num"] >= 2:
            period = "lunch"
        else:
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


def validate_pizza_opening_run(context):
    visits = _visits(context, PIZZA)
    if len(visits) != 1:
        return False, "Schedule exactly one Ijaemo Pizza visit."
    stop = visits[0]
    intervals = _opening_intervals(context["places"][stop["place_id"]], SECOND_DAY)
    if not intervals or _start(stop) != min(opening for opening, _ in intervals):
        return False, "Visit Ijaemo Pizza at opening time on Nov 17."
    return True, ""


def validate_tonshow_dinner(context):
    visits = _visits(context, TONSHOW)
    if len(visits) != 1 or _start(visits[0]) != datetime(2026, 11, 17, 17):
        return False, "Visit Tonshow on Nov 17 at 17:00."
    return True, ""


def validate_village_after_pizza(context):
    pizza = _visits(context, PIZZA)
    village = _visits(context, {VILLAGE})
    if len(village) != 1:
        return False, "Schedule exactly one Huinnyeoul Culture Village visit."
    if not pizza or _start(village[0]).date() != SECOND_DAY or _start(village[0]) < _end(pizza[0]):
        return False, "Visit Huinnyeoul Culture Village after Ijaemo Pizza on Nov 17."
    return True, ""


def validate_cafe_after_village(context):
    village = _visits(context, {VILLAGE})
    cafe = _visits(context, {CAFE})
    if len(cafe) != 1:
        return False, "Schedule exactly one Ha ille cafe visit."
    if not village or _start(cafe[0]).date() != SECOND_DAY or _start(cafe[0]) < _end(village[0]):
        return False, "Visit Ha ille cafe after Huinnyeoul Culture Village on Nov 17."
    segments = context["segments"]
    village_index = segments.index(village[0])
    following = segments[village_index + 1:village_index + 3]
    if (
        len(following) != 2
        or following[0]["segment_type"] != "LEG"
        or following[1] != cafe[0]
    ):
        return False, "Go directly from Huinnyeoul Culture Village to Ha ille cafe."
    return True, ""


# Each turn adds constraints while retaining all preceding turns' constraints.
TURN_CONSTRAINTS = {
    1: (
        validate_request_status,
        validate_trip_dates,
        validate_arrival,
        validate_departure,
        validate_accommodation,
        validate_requested_places,
        validate_minimum_durations,
        validate_opening_hours,
        validate_meal_periods,
    ),
    2: (validate_pizza_opening_run,),
    3: (validate_tonshow_dinner,),
    4: (validate_village_after_pizza, validate_cafe_after_village),
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
