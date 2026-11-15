# Generated turn-level scenario expectations matching 108.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-12-02T10:00',
 'end': '2026-12-06T18:00',
 'origin': '부산역',
 'destination': '부산역',
 'hotel': '아난티 코브',
 'turns': [[],
           [{'op': 'add',
             'place': '롯데월드 어드벤처 부산',
             'day': 2,
             'at': '13:00',
             'duration': 240,
             'until': '17:00'}],
           [{'op': 'add', 'place': '송정해녀집 기장오시리아점', 'day': 2, 'at': '18:30', 'meal': 'dinner'}],
           [{'op': 'reject'}],
           [{'op': 'add', 'place': '칠암사계', 'day': 3, 'at': '15:00', 'duration': 90}],
           [{'op': 'add', 'place': '해동용궁사', 'day': 4, 'at': '11:00'}],
           [{'op': 'add', 'place': '시랑이랑', 'day': 4, 'after': '해동용궁사'}],
           [{'op': 'replace', 'old': '시랑이랑', 'place': '오션브리즈', 'day': 4}],
           [{'op': 'move', 'place': '칠암사계', 'day': 3, 'at': '16:00'}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(108, SPEC, turn_num, itinerary_id, request_status)
