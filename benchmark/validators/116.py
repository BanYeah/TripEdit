"""Turn-by-turn itinerary checks for scenario 116."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-11T09:00",
    "end": "2026-12-13T20:00",
    "origin": "부산서부버스터미널",
    "destination": "부산서부버스터미널",
    "hotel": "페어필드 바이메리어트 부산송도비치",
    "turns": [
        [],
        [{'op': 'add', 'place': '을숙도철새공원', 'day': 2, 'at': '10:00'}],
        [{'op': 'add', 'place': '블랙업커피 을숙도점', 'day': 2, 'after': '을숙도철새공원'}],
        [
            {
                'op': 'replace',
                'old': '을숙도철새공원',
                'place': '을숙도철새공원',
                'day': 2,
                'at': '10:30',
                'until': '12:00',
            },
        ],
        [{'op': 'remove', 'place': '블랙업커피 을숙도점', 'day': 2}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(116, SPEC, turn_num, itinerary_id, request_status)
