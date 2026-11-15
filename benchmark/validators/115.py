"""Turn-by-turn itinerary checks for scenario 115."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-10T09:00",
    "end": "2026-12-14T20:00",
    "origin": "구포역",
    "destination": "부산역",
    "hotel": "호텔농심",
    "turns": [
        [],
        [{'op': 'add', 'place': '부산화명수목원', 'day': 1, 'at': '13:00'}],
        [{'op': 'add', 'place': '충렬사', 'day': 2, 'at': '11:00'}],
        [{'op': 'add', 'place': '모모스커피 부산본점', 'day': 2, 'at': '15:00', 'after': '충렬사'}],
        [{'op': 'add', 'place': '부산시민공원', 'day': 4, 'at': '14:00'}],
        [{'op': 'move', 'place': '부산시민공원', 'day': 4, 'at': '16:00'}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(115, SPEC, turn_num, itinerary_id, request_status)
