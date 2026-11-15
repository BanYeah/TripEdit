# Generated turn-level scenario expectations matching 107.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-12-01T11:00',
 'end': '2026-12-05T20:00',
 'origin': '부산역',
 'destination': '신해운대역',
 'hotel': '시그니엘 부산',
 'turns': [[],
           [{'op': 'add', 'place': '부산엑스더스카이', 'day': 1, 'at': '16:00'}],
           [{'op': 'add', 'place': '해동용궁사', 'day': 2, 'at': '10:00', 'duration': 70}],
           [{'op': 'add', 'place': '송정해녀집 기장오시리아점', 'day': 2, 'at': '12:30', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '칠암사계', 'day': 2, 'after': '송정해녀집 기장오시리아점'}],
           [{'op': 'add', 'place': '해운대블루라인파크 청사포정거장', 'day': 3, 'at': '16:00'}],
           [{'op': 'add',
             'place': '청사포다릿돌전망대',
             'day': 3,
             'duration': 30,
             'after': '해운대블루라인파크 청사포정거장'}],
           [{'op': 'replace', 'old': '칠암사계', 'place': '웨이브온커피', 'day': 2}],
           [{'op': 'move', 'place': '부산엑스더스카이', 'day': 1, 'at': '17:30'}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(107, SPEC, turn_num, itinerary_id, request_status)
