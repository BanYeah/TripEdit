# Generated turn-level scenario expectations matching 106.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-11-30T10:00',
 'end': '2026-12-04T19:00',
 'origin': '부산역',
 'destination': '부산역',
 'hotel': '롯데호텔 부산',
 'turns': [[],
           [{'op': 'add', 'place': '부산시민공원', 'day': 1, 'at': '14:00'}],
           [{'op': 'add', 'place': '롯데백화점 부산본점', 'day': 2, 'at': '13:00'}],
           [{'op': 'add', 'place': '수변최고돼지국밥 서면롯데점', 'day': 2, 'at': '18:30', 'meal': 'dinner'}],
           [{'op': 'add', 'place': '부산어린이대공원', 'day': 3, 'at': '11:00'}],
           [{'op': 'add', 'place': '블랙업커피 서면본점', 'day': 4, 'at': '15:00', 'duration': 60}],
           [{'op': 'add',
             'place': '춘하추동밀면 서면본점',
             'day': 4,
             'at': '12:00',
             'before': '블랙업커피 서면본점',
             'meal': 'lunch'}],
           [{'op': 'replace', 'old': '수변최고돼지국밥 서면롯데점', 'place': '바오하우스', 'day': 2, 'at': '18:30'}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(106, SPEC, turn_num, itinerary_id, request_status)
