"""Turn-by-turn itinerary checks for scenario 118."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-13T09:00",
    "end": "2026-12-15T20:00",
    "origin": "신해운대역",
    "destination": "부산역",
    "hotel": "웨스틴조선 부산",
    "turns": [
        [],
        [{'op': 'add', 'place': '동백섬', 'day': 1, 'at': '14:00'}],
        [{'op': 'add', 'place': '모모스커피 마린시티점', 'day': 1, 'before': '동백섬'}],
        [{'op': 'move', 'place': '동백섬', 'day': 1, 'at': '16:00'}],
        [{'op': 'add', 'place': '신세계백화점 센텀시티점', 'day': 3, 'at': '11:30'}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(118, SPEC, turn_num, itinerary_id, request_status)
