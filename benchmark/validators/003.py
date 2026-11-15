"""Cumulative constraints for the eleven turns of scenario 003."""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from database import connect

ARRIVAL = datetime(2026, 11, 20, 20)
DEPARTURE = datetime(2026, 11, 22, 15)

STATION = 8329752
HOTEL = 21025068
MADDOGS = 25505923

BEACH = 8202423
TONSHOW = {1901662463, 590377149, 704518356}
DINNER = {591454373, 828025978, 2090734948}
YOKO = {596401302, 2031795174}
CULTURE = 771465406
CAFE = 1817223839
STAIRS = 21546007
ROAD = 24544632
WORKSHOP = 19928566
CHINATOWN = 13114460
DEPARTMENT = 7969139
SECOND_DAY = datetime(2026, 11, 21).date()
THIRD_DAY = DEPARTURE.date()

# Each group represents exactly one requested visit, from its introduction onward.
REQUESTED_VISITS = {
    2: ({MADDOGS},),
    3: ({BEACH},),
    4: (TONSHOW,),
    5: ({CULTURE},),
    6: ({CAFE}, DINNER),
    7: ({STAIRS},),
    8: ({ROAD}, {WORKSHOP}),
    9: ({CHINATOWN},),
    10: ({DEPARTMENT},),
    11: (YOKO,),
}


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
        return False, "Trip must run from Nov 20 20:00 to Nov 22 15:00."
    for segment in context["segments"]:
        if not ARRIVAL <= _start(segment) < _end(segment) <= DEPARTURE:
            return False, "Segments must stay within the trip dates."
    return True, ""


def validate_arrival(context):
    stops = context["stops"]
    if not stops or stops[0]["place_id"] != STATION or _start(stops[0]) != ARRIVAL:
        return False, "Trip must start at Busan Station on Nov 20 at 20:00."
    minutes = int(context["places"][STATION]["arrival_after"])
    if _end(stops[0]) < ARRIVAL + timedelta(minutes=minutes):
        return False, f"Allow at least {minutes} minutes after arrival at Busan Station."
    return True, ""


def validate_departure(context):
    stops = context["stops"]
    if not stops or stops[-1]["place_id"] != STATION or _end(stops[-1]) != DEPARTURE:
        return False, "Trip must end at Busan Station on Nov 22 at 15:00."
    minutes = int(context["places"][STATION]["departure_before"])
    if _start(stops[-1]) > DEPARTURE - timedelta(minutes=minutes):
        return False, f"Allow at least {minutes} minutes before departure at Busan Station."
    return True, ""


def validate_accommodation(context):
    hotels = _visits(context, {HOTEL})
    if not hotels:
        return False, "Stay at Park Hyatt Busan."
    if any(
        context["places"][stop["place_id"]]["category"] == "accommodation"
        and stop["place_id"] != HOTEL
        for stop in context["stops"]
    ):
        return False, "All accommodation stays must be at Park Hyatt Busan."

    place = context["places"][HOTEL]
    midnight = datetime.combine(ARRIVAL.date(), datetime.min.time())

    def at(value):
        hours, minutes = map(int, value.split(":"))
        return midnight + timedelta(hours=hours, minutes=minutes)

    opening, closing = map(at, place["check-in"].split("-"))
    if closing <= opening:
        closing += timedelta(days=1)
    # Check-in applies only to the first arrival, not subsequent hotel returns.
    if not opening <= _start(hotels[0]) <= closing:
        return False, "First arrival at Park Hyatt Busan must be within the Nov 20 check-in window."
    checkout = at(place["check-out"]) + timedelta(days=2)
    if _end(hotels[-1]) > checkout:
        return False, "Leave Park Hyatt Busan by check-out time on Nov 22."

    for day in (21, 22):
        start = datetime(2026, 11, day)
        end = start + timedelta(hours=6)
        covered = start
        for stop in hotels:
            if _start(stop) <= covered < _end(stop):
                covered = _end(stop)
        if covered < end:
            return False, f"Stay at Park Hyatt Busan throughout Nov {day} 00:00-06:00."
    return True, ""


def validate_requested_places(context):
    allowed = {STATION, HOTEL}
    for turn, groups in REQUESTED_VISITS.items():
        if turn > context["turn_num"]:
            continue
        for group in groups:
            allowed |= group
            visits = _visits(context, group)
            if len(visits) != 1:
                names = ", ".join(context["places"][key]["name"] for key in sorted(group))
                return False, f"Schedule exactly one visit to: {names}."
            day = ARRIVAL.date() if turn <= 3 else THIRD_DAY if turn == 11 else SECOND_DAY
            if _start(visits[0]).date() != day or _end(visits[0]).date() != day:
                return False, f"Visit {context['places'][visits[0]['place_id']]['name']} on {day}."
    if any(stop["place_id"] not in allowed for stop in context["stops"]):
        return False, "Do not add unrequested places."
    return True, ""


def validate_minimum_durations(context):
    for stop in context["stops"]:
        place = context["places"][stop["place_id"]]
        duration = _end(stop) - _start(stop)
        # The user explicitly shortens the beach stay to meet check-in.
        if stop["place_id"] == BEACH and context["turn_num"] >= 3:
            continue
        if stop["place_id"] == CHINATOWN and context["turn_num"] >= 9:
            if duration != timedelta(minutes=30):
                return False, "Visit Chinatown for the requested 30 minutes."
        elif "min_duration" in place and duration < timedelta(minutes=int(place["min_duration"])):
            return False, f"Visit to {place['name']} must last at least {place['min_duration']} minutes."
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


def validate_maddogs_after_arrival(context):
    visits = _visits(context, {MADDOGS})
    if len(visits) != 1:
        return False, "Schedule exactly one Maddogs Gwangalli visit."
    stops = context["stops"]
    if len(stops) < 2 or stops[1] != visits[0]:
        return False, "Go to Maddogs Gwangalli directly after arriving at Busan Station."
    if _start(visits[0]).date() != ARRIVAL.date():
        return False, "Visit Maddogs Gwangalli on Nov 20."
    # The explicit late-night visit overrides the default dinner period.
    # Opening hours and minimum duration still apply.
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
        if stop["place_id"] == MADDOGS:
            period = "dinner"  # Explicit arrival-night meal overrides default hours.
        elif midnight + timedelta(hours=11) <= start < end <= midnight + timedelta(hours=15):
            period = "lunch"
        elif midnight + timedelta(hours=17) <= start < end <= midnight + timedelta(hours=21):
            period = "dinner"
        else:
            return False, "Restaurant visits must fit a lunch or dinner period."
        if stop["place_id"] in DINNER and period != "dinner":
            return False, "Visit The Bareun restaurant for dinner."
        if stop["place_id"] in YOKO and period != "lunch":
            return False, "Visit Yoko for lunch."
        key = (start.date(), period)
        if key in meals:
            return False, "Schedule at most one restaurant per meal period."
        meals.add(key)
    return True, ""


def validate_beach_before_checkin(context):
    stops = context["stops"]
    if len(stops) < 4 or [stop["place_id"] for stop in stops[:4]] != [STATION, MADDOGS, BEACH, HOTEL]:
        return False, "Visit Busan Station, Maddogs, Gwangalli Beach, then the hotel."
    place = context["places"][HOTEL]
    hours, minutes = map(int, place["check-in"].split("-")[1].split(":"))
    deadline = datetime.combine(ARRIVAL.date(), datetime.min.time()) + timedelta(hours=hours, minutes=minutes - 10)
    if _start(stops[3]) > deadline:
        return False, "Reach the hotel at least 10 minutes before the first-night check-in deadline."
    return True, ""


def validate_tonshow_opening_run(context):
    stop = _visits(context, TONSHOW)[0]
    intervals = _opening_intervals(context["places"][stop["place_id"]], SECOND_DAY)
    if not intervals or _start(stop) != min(opening for opening, _ in intervals):
        return False, "Visit Tonshow at opening time on Nov 21."
    return True, ""


def validate_cafe_before_dinner(context):
    if _end(_visits(context, {CAFE})[0]) > _start(_visits(context, DINNER)[0]):
        return False, "Visit Oporto before dinner."
    return True, ""


def validate_chinatown_before_dinner(context):
    if _end(_visits(context, {CHINATOWN})[0]) > _start(_visits(context, DINNER)[0]):
        return False, "Visit Chinatown before dinner."
    return True, ""


def validate_shopping_after_dinner(context):
    shopping = _visits(context, {DEPARTMENT})[0]
    if _start(shopping) < _end(_visits(context, DINNER)[0]):
        return False, "Shop at Shinsegae after dinner."
    intervals = _opening_intervals(context["places"][DEPARTMENT], SECOND_DAY)
    if not intervals or _end(shopping) != max(closing for _, closing in intervals):
        return False, "Stay at Shinsegae until closing time."
    stops = context["stops"]
    index = stops.index(shopping)
    if index + 1 >= len(stops) or stops[index + 1]["place_id"] != HOTEL:
        return False, "Return to the hotel directly after shopping."
    return True, ""


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
    2: (validate_maddogs_after_arrival,),
    3: (validate_beach_before_checkin,),
    4: (validate_tonshow_opening_run,),
    5: (),  # Presence and day are checked by validate_requested_places.
    6: (validate_cafe_before_dinner,),
    7: (),
    8: (),
    9: (validate_chinatown_before_dinner,),
    10: (validate_shopping_after_dinner,),
    11: (),
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
