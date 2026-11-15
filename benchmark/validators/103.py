# Generated turn-level scenario expectations matching 103.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-11-25T09:00',
 'end': '2026-11-27T20:00',
 'origin': '부산역',
 'destination': '신해운대역',
 'hotel': '신라스테이 해운대',
 'turns': [[],
           [{'op': 'add', 'place': '해목', 'day': 1, 'at': '12:30', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '해운대해수욕장', 'day': 1, 'at': '15:00', 'duration': 90}],
           [{'op': 'add', 'place': '해운대블루라인파크 미포정거장', 'day': 2, 'at': '10:00'}],
           [{'op': 'add',
             'place': '스탠다드브레드 해운대',
             'day': 2,
             'at': '12:00',
             'after': '해운대블루라인파크 미포정거장'}],
           [{'op': 'add', 'place': '부산엑스더스카이', 'day': 3, 'at': '15:00'}],
           [{'op': 'replace',
             'old': '스탠다드브레드 해운대',
             'place': '블랙업커피 해운대점',
             'day': 2,
             'at': '12:00'}],
           [{'op': 'move', 'place': '해운대해수욕장', 'day': 1, 'at': '16:30'}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(103, SPEC, turn_num, itinerary_id, request_status)
