"""Turn-by-turn itinerary checks for scenario 114."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-09T09:00",
    "end": "2026-12-11T20:00",
    "origin": "부산역",
    "destination": "신해운대역",
    "hotel": "마티에오시리아호텔",
    "turns": [
        [],
        [{'op': 'reject'}],
        [{'op': 'add', 'place': '국립부산과학관', 'day': 2, 'at': '14:30'}],
        [{'op': 'add', 'place': '국립수산과학관', 'day': 3, 'at': '10:00'}],
        [{'op': 'move', 'place': '국립수산과학관', 'day': 3, 'at': '11:00'}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(114, SPEC, turn_num, itinerary_id, request_status)
