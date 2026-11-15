# Generated turn-level scenario expectations matching 102.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-11-24T11:00',
 'end': '2026-11-26T19:00',
 'origin': '부산역',
 'destination': '부산역',
 'hotel': '아스티 호텔',
 'turns': [[],
           [{'op': 'add', 'place': '초량차이나타운', 'day': 1, 'at': '13:00', 'duration': 60}],
           [{'op': 'add', 'place': '본전돼지국밥', 'day': 1, 'at': '17:30', 'meal': 'dinner'}],
           [{'op': 'add', 'place': '168계단', 'day': 1, 'duration': 30, 'after': '본전돼지국밥'}],
           [{'op': 'add', 'place': '이재모피자 부산역점', 'day': 2, 'at': '12:00', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '노티스', 'day': 2, 'after': '이재모피자 부산역점'}],
           [{'op': 'remove', 'place': '노티스', 'day': 2}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(102, SPEC, turn_num, itinerary_id, request_status)
