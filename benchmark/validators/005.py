"""Cumulative constraints for the eleven turns of scenario 005."""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from database import connect

ARRIVAL = datetime(2026, 11, 6, 20)
DEPARTURE = datetime(2026, 11, 8, 13)
STATION = 20174971
HOTEL = 327520717
BEACH = 7913306
ISLAND = 8257954
COD = 7958381
MIPO = 188403018
CHEONGSAPO = 321220117
OBSERVATORY = 484076440
SONGJEONG = 188458716
TEMPLE = 8606230
CAFE = 1504874222
DINNER = 16610024
YACHT = 499053210
SUBYEON = {14635779, 769611948, 596548360}
MUSEUM = 13312019
SECOND_DAY = ARRIVAL.date() + timedelta(days=1)


def travel_time_overrides(turn_num):
    # User-specified train times become available only in turn 7.
    if turn_num < 7:
        return {}
    return {
        (MIPO, CHEONGSAPO, "TRANSIT"): 9,
        (CHEONGSAPO, OBSERVATORY, "TRANSIT"): 3,
        (OBSERVATORY, SONGJEONG, "TRANSIT"): 9,
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
        return False, "Trip must run from Nov 6 20:00 to Nov 8 13:00."
    for segment in context["segments"]:
        if not ARRIVAL <= _start(segment) < _end(segment) <= DEPARTURE:
            return False, "Segments must stay within the trip dates."
    return True, ""


def validate_arrival(context):
    stops = context["stops"]
    if not stops or stops[0]["place_id"] != STATION or _start(stops[0]) != ARRIVAL:
        return False, "Trip must start at Sinhaeundae Station on Nov 6 at 20:00."
    minutes = int(context["places"][STATION]["arrival_after"])
    if _end(stops[0]) < ARRIVAL + timedelta(minutes=minutes):
        return False, f"Allow at least {minutes} minutes after arrival at Sinhaeundae Station."
    return True, ""


def validate_departure(context):
    stops = context["stops"]
    if not stops or stops[-1]["place_id"] != STATION or _end(stops[-1]) != DEPARTURE:
        return False, "Trip must end at Sinhaeundae Station on Nov 8 at 13:00."
    minutes = int(context["places"][STATION]["departure_before"])
    if _start(stops[-1]) > DEPARTURE - timedelta(minutes=minutes):
        return False, f"Allow at least {minutes} minutes before departure at Sinhaeundae Station."
    return True, ""


def validate_accommodation(context):
    hotels = _visits(context, {HOTEL})
    if not hotels:
        return False, "Stay at Signiel Busan."
    if any(
        context["places"][stop["place_id"]]["category"] == "accommodation"
        and stop["place_id"] != HOTEL
        for stop in context["stops"]
    ):
        return False, "All accommodation stays must be at Signiel Busan."
    # The last hotel visit in turn 11 is luggage collection after check-out.
    stays = hotels[:-1] if context["turn_num"] >= 11 else hotels
    if not stays:
        return False, "Hotel stays must precede the luggage collection visit."
    place = context["places"][HOTEL]
    midnight = datetime.combine(ARRIVAL.date(), datetime.min.time())

    def at(value):
        hours, minutes = map(int, value.split(":"))
        return midnight + timedelta(hours=hours, minutes=minutes)

    opening, closing = map(at, place["check-in"].split("-"))
    if closing <= opening:
        closing += timedelta(days=1)
    if not opening <= _start(stays[0]) <= closing:
        return False, "Check in at Signiel Busan within the Nov 6 check-in window."
    checkout = at(place["check-out"]) + (DEPARTURE.date() - ARRIVAL.date())
    if _end(stays[-1]) > checkout:
        return False, "Check out of Signiel Busan by 11:00 on Nov 8."
    for offset in (1, 2):
        start = midnight + timedelta(days=offset)
        end = start + timedelta(hours=6)
        covered = start
        for stop in stays:
            if _start(stop) <= covered < _end(stop):
                covered = _end(stop)
        if covered < end:
            return False, f"Stay at Signiel Busan throughout {start.date()} 00:00-06:00."
    return True, ""


def validate_requested_places(context):
    turn = context["turn_num"]
    groups = []
    if turn >= 3:
        groups += [({BEACH}, ARRIVAL.date()), ({ISLAND}, ARRIVAL.date())]
    if turn >= 4:
        groups.append(({COD}, SECOND_DAY))
    if turn >= 5:
        groups += [( {place}, SECOND_DAY) for place in (MIPO, CHEONGSAPO, OBSERVATORY, SONGJEONG)]
    if turn >= 6:
        groups.append(({CAFE}, SECOND_DAY))
    if turn >= 8:
        groups += [({TEMPLE}, SECOND_DAY), ({DINNER}, SECOND_DAY)]
    if turn >= 9:
        groups.append(({YACHT}, SECOND_DAY))
    if turn >= 10:
        groups += [(SUBYEON, DEPARTURE.date()), ({MUSEUM}, DEPARTURE.date())]
    allowed = {STATION, HOTEL}
    for group, day in groups:
        allowed |= group
        visits = _visits(context, group)
        if len(visits) != 1:
            names = ", ".join(context["places"][key]["name"] for key in sorted(group))
            return False, f"Schedule exactly one visit to: {names}."
        if _start(visits[0]).date() != day or _end(visits[0]).date() != day:
            return False, f"Visit {context['places'][visits[0]['place_id']]['name']} on {day}."
    if any(stop["place_id"] not in allowed for stop in context["stops"]):
        return False, "Do not add unrequested places."
    return True, ""


def validate_minimum_durations(context):
    exact = {}
    if context["turn_num"] >= 3:
        exact.update({BEACH: 10, ISLAND: 20})
    if context["turn_num"] >= 7:
        exact.update({CHEONGSAPO: 1, OBSERVATORY: 30})
    for stop in context["stops"]:
        place = context["places"][stop["place_id"]]
        duration = _end(stop) - _start(stop)
        if stop["place_id"] in exact:
            minutes = exact[stop["place_id"]]
            if duration != timedelta(minutes=minutes):
                return False, f"Visit to {place['name']} must last the requested {minutes} minutes."
        elif "min_duration" in place:
            minutes = int(place["min_duration"])
            if duration < timedelta(minutes=minutes):
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
        if stop["place_id"] == COD or stop["place_id"] in SUBYEON:
            if not midnight + timedelta(hours=6) <= start < end <= midnight + timedelta(hours=11):
                return False, "Requested breakfast visits must fit 06:00-11:00."
            period = "breakfast"
        elif midnight + timedelta(hours=11) <= start < end <= midnight + timedelta(hours=15):
            period = "lunch"
        elif midnight + timedelta(hours=17) <= start < end <= midnight + timedelta(hours=21):
            period = "dinner"
        else:
            return False, "Restaurant visits must fit a lunch or dinner period."
        if stop["place_id"] == DINNER and period != "dinner":
            return False, "Visit Solnaeum for dinner."
        key = (start.date(), period)
        if key in meals:
            return False, "Schedule at most one restaurant per meal period."
        meals.add(key)
    return True, ""


def _ordered(context, place_ids, *, direct=False):
    stops = context["stops"]
    for origin, destination in zip(place_ids, place_ids[1:]):
        a = next(index for index, stop in enumerate(stops) if stop["place_id"] == origin)
        b = next(index for index, stop in enumerate(stops) if stop["place_id"] == destination)
        if a >= b or (direct and b != a + 1):
            return False
    return True


def validate_immediate_checkin(context):
    if len(context["stops"]) < 2 or context["stops"][1]["place_id"] != HOTEL:
        return False, "Go directly to Signiel Busan after arriving at Sinhaeundae Station."
    return True, ""


def validate_evening_walk(context):
    stops = context["stops"]
    if len(stops) < 5 or [stop["place_id"] for stop in stops[:5]] != [STATION, HOTEL, BEACH, ISLAND, HOTEL]:
        return False, "After check-in, visit Haeundae Beach, Dongbaek Island, then return to the hotel."
    for index in (3, 5, 7):
        if context["segments"][index]["transport_mode"] != "WALK":
            return False, "Walk all three legs of the first-night outing."
    if _start(stops[4]).date() != ARRIVAL.date():
        return False, "Return to the hotel on Nov 6 after the evening walk."
    return True, ""


def validate_blueline_route(context):
    if not _ordered(context, [COD, MIPO, CHEONGSAPO, OBSERVATORY, SONGJEONG], direct=True):
        return False, "After breakfast, visit Mipo, Cheongsapo, Daritdol Observatory, then Songjeong."
    for index, leg in enumerate(context["segments"]):
        if leg["segment_type"] != "LEG":
            continue
        origin = context["segments"][index - 1]
        if origin["place_id"] == MIPO:
            if _end(origin) != datetime(2026, 11, 7, 10) or _start(leg) != datetime(2026, 11, 7, 10):
                return False, "Depart Mipo for Cheongsapo at 10:00 on Nov 7."
    return True, ""


def validate_cafe_after_songjeong(context):
    if not _ordered(context, [SONGJEONG, CAFE]):
        return False, "Visit Chilam Sagye after Songjeong Station."
    return True, ""


def validate_train_times(context):
    overrides = travel_time_overrides(context["turn_num"])
    segments = context["segments"]
    for index in range(1, len(segments), 2):
        leg = segments[index]
        pair = (segments[index - 1]["place_id"], segments[index + 1]["place_id"], "TRANSIT")
        if pair in overrides:
            minutes = overrides[pair]
            if leg["transport_mode"] != "TRANSIT" or _end(leg) - _start(leg) != timedelta(minutes=minutes):
                return False, f"Use the requested train route of {minutes} minutes for LEG {leg['segment_id']}."
    return True, ""


def validate_temple_then_dinner(context):
    if not _ordered(context, [CAFE, TEMPLE, DINNER]):
        return False, "Visit Haedong Yonggungsa after Chilam Sagye, then have dinner at Solnaeum."
    return True, ""


def validate_yacht_then_hotel(context):
    yacht = _visits(context, {YACHT})[0]
    if not _ordered(context, [DINNER, YACHT]):
        return False, "Visit Busan Yacht Tour after dinner."
    if _start(yacht) > datetime(2026, 11, 7, 19):
        return False, "Arrive for Busan Yacht Tour by 19:00 on Nov 7."
    stops = context["stops"]
    index = stops.index(yacht)
    if index + 1 >= len(stops) or stops[index + 1]["place_id"] != HOTEL:
        return False, "Return directly to the hotel after the yacht tour."
    return True, ""


def validate_sunday_breakfast_then_museum(context):
    breakfast = _visits(context, SUBYEON)[0]
    museum = _visits(context, {MUSEUM})[0]
    if _end(breakfast) > _start(museum):
        return False, "Visit Goeun Museum of Photography after Sunday breakfast."
    return True, ""


def validate_luggage_collection(context):
    stops = context["stops"]
    museum_index = next(index for index, stop in enumerate(stops) if stop["place_id"] == MUSEUM)
    if [stop["place_id"] for stop in stops[museum_index:]] != [MUSEUM, HOTEL, STATION]:
        return False, "After the museum, collect luggage at Signiel Busan before going to Sinhaeundae Station."
    hotels = _visits(context, {HOTEL})
    # The preceding stay must end on departure day (check-out and bag drop).
    if len(hotels) < 2 or _end(hotels[-2]).date() != DEPARTURE.date():
        return False, "Check out and leave luggage at the hotel on Nov 8 before collecting it later."
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
    2: (validate_immediate_checkin,),
    3: (validate_evening_walk,),
    4: (),  # Saturday breakfast is checked by the common scenario rules.
    5: (validate_blueline_route,),
    6: (validate_cafe_after_songjeong,),
    7: (validate_train_times,),
    8: (validate_temple_then_dinner,),
    9: (validate_yacht_then_hotel,),
    10: (validate_sunday_breakfast_then_museum,),
    11: (validate_luggage_collection,),
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
