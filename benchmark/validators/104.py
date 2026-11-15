# Generated turn-level scenario expectations matching 104.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-11-26T09:30',
 'end': '2026-11-28T19:30',
 'origin': '부산역',
 'destination': '부산역',
 'hotel': '호메르스호텔',
 'turns': [[],
           [{'op': 'add', 'place': '광안리해수욕장', 'day': 1, 'at': '14:00', 'duration': 90}],
           [{'op': 'add', 'place': '톤쇼우 광안점', 'day': 1, 'at': '18:30', 'meal': 'dinner'}],
           [{'op': 'add', 'place': '히떼로스터리 광안점', 'day': 1, 'duration': 60, 'before': '톤쇼우 광안점'}],
           [{'op': 'add', 'place': '남천가야밀면', 'day': 2, 'at': '11:30', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '부산요트투어', 'day': 2, 'at': '15:00'}],
           [{'op': 'move', 'place': '부산요트투어', 'day': 2, 'at': '17:00'}],
           [{'op': 'remove', 'place': '히떼로스터리 광안점', 'day': 1}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(104, SPEC, turn_num, itinerary_id, request_status)
