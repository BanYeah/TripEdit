"""Turn-by-turn itinerary checks for scenario 111."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-07T10:00",
    "end": "2026-12-09T19:00",
    "origin": "부산역",
    "destination": "부산역",
    "hotel": "코모도호텔 부산",
    "turns": [
        [],
        [
            {
                'op': 'add',
                'place': '부산박물관',
                'day': 2,
                'at': '10:00',
                'until': '10:45',
                'duration': 45,
            },
        ],
        [{'op': 'add', 'place': '오륙도스카이워크', 'day': 2, 'at': '14:30'}],
        [
            {
                'op': 'replace',
                'old': '부산박물관',
                'place': '부산박물관',
                'day': 2,
                'at': '11:00',
                'until': '11:45',
            },
        ],
        [{'op': 'remove', 'place': '오륙도스카이워크', 'day': 2}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(111, SPEC, turn_num, itinerary_id, request_status)
