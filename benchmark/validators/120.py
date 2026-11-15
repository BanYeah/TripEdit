"""Turn-by-turn itinerary checks for scenario 120."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-15T09:00",
    "end": "2026-12-19T21:00",
    "origin": "김해국제공항 국내선청사",
    "destination": "김해국제공항 국내선청사",
    "hotel": "어반스테이 부산시청",
    "turns": [
        [],
        [{'op': 'add', 'place': '부산시민공원', 'day': 1, 'at': '15:00'}],
        [{'op': 'add', 'place': '식당3선 연제점', 'day': 2, 'at': '12:00', 'meal': 'lunch'}],
        [{'op': 'add', 'place': '부산사직종합운동장 사직야구장', 'day': 4, 'at': '17:30', 'until': '21:30'}],
        [{'op': 'reject'}],
        [{'op': 'add', 'place': '연산옥 샤브칼국수', 'day': 3, 'at': '18:00', 'meal': 'dinner'}],
        [{'op': 'remove', 'place': '식당3선 연제점', 'day': 2}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(120, SPEC, turn_num, itinerary_id, request_status)
