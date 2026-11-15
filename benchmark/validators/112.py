"""Turn-by-turn itinerary checks for scenario 112."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-08T09:00",
    "end": "2026-12-10T20:00",
    "origin": "부산역",
    "destination": "신해운대역",
    "hotel": "센텀프리미어호텔",
    "turns": [
        [],
        [{'op': 'add', 'place': '식당3선 센텀점', 'day': 2, 'at': '12:00', 'meal': 'lunch'}],
        [{'op': 'add', 'place': '고은사진미술관', 'day': 2, 'after': '식당3선 센텀점'}],
        [{'op': 'replace', 'old': '식당3선 센텀점', 'place': '금수복국 해운대본점', 'day': 2}],
        [{'op': 'move', 'place': '고은사진미술관', 'day': 2, 'at': '15:00'}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(112, SPEC, turn_num, itinerary_id, request_status)
