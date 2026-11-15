# Generated turn-level scenario expectations matching 110.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-12-04T10:00',
 'end': '2026-12-06T19:00',
 'origin': '김해국제공항 국내선청사',
 'destination': '김해국제공항 국내선청사',
 'hotel': '라발스호텔',
 'turns': [[],
           [{'op': 'add', 'place': '태종대유원지', 'day': 1, 'at': '15:00', 'duration': 90}],
           [{'op': 'add', 'place': '올바릇식당 영도점', 'day': 1, 'at': '18:00', 'meal': 'dinner'}],
           [{'op': 'add', 'place': '국립해양박물관', 'day': 2, 'at': '10:30', 'duration': 60}],
           [{'op': 'add', 'place': '올바릇식당 영도점', 'day': 2, 'at': '13:00', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '흰여울문화마을', 'day': 2, 'at': '15:00', 'duration': 60}],
           [{'op': 'add', 'place': '아르떼뮤지엄 부산', 'day': 2, 'at': '17:00'}],
           [{'op': 'reject'}],
           [{'op': 'add', 'place': '톤쇼우 남포점', 'day': 3, 'at': '12:00', 'meal': 'lunch'}],
           [{'op': 'remove', 'place': '국립해양박물관', 'day': 2}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(110, SPEC, turn_num, itinerary_id, request_status)
