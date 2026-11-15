"""Turn-by-turn itinerary checks for scenario 113."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-08T10:00",
    "end": "2026-12-10T20:00",
    "origin": "부산역",
    "destination": "구포역",
    "hotel": "아스티 호텔",
    "turns": [
        [],
        [{'op': 'add', 'place': '문화공감 수정', 'day': 1, 'at': '14:00'}],
        [{'op': 'add', 'place': '문화공감 수정', 'day': 2, 'at': '15:30'}],
        [{'op': 'remove', 'place': '문화공감 수정', 'day': 2}],
        [{'op': 'add', 'place': '임시수도기념관', 'day': 3, 'at': '10:30'}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(113, SPEC, turn_num, itinerary_id, request_status)
