"""Turn-by-turn itinerary checks for scenario 117."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-12T09:00",
    "end": "2026-12-14T21:00",
    "origin": "부산종합버스터미널",
    "destination": "부전역",
    "hotel": "롯데호텔 부산",
    "turns": [
        [],
        [{'op': 'add', 'place': '서면밀면', 'day': 1, 'at': '12:00', 'meal': 'lunch'}],
        [{'op': 'reject'}],
        [{'op': 'add', 'place': '기장손칼국수', 'day': 2, 'at': '12:30', 'meal': 'lunch'}],
        [{'op': 'remove', 'place': '서면밀면', 'day': 1}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(117, SPEC, turn_num, itinerary_id, request_status)
