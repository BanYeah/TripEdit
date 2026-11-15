"""Turn-by-turn itinerary checks for scenario 119."""
from ._scenario_common import validate_scenario

SPEC = {
    "start": "2026-12-14T10:00",
    "end": "2026-12-16T20:00",
    "origin": "부산역",
    "destination": "부산항국제여객터미널",
    "hotel": "라발스호텔",
    "turns": [
        [],
        [{'op': 'add', 'place': '동삼동패총전시관', 'day': 2, 'at': '11:00'}],
        [{'op': 'add', 'place': '태종대유원지', 'day': 2, 'at': '14:00'}],
        [{'op': 'replace', 'old': '동삼동패총전시관', 'place': '국립해양박물관', 'day': 2}],
        [{'op': 'add', 'place': '재기돼지국밥', 'day': 2, 'at': '18:00', 'meal': 'dinner'}],
        [{'op': 'remove', 'place': '태종대유원지', 'day': 2}],
    ],
}


def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(119, SPEC, turn_num, itinerary_id, request_status)
