# Generated turn-level scenario expectations matching 105.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-11-27T10:00',
 'end': '2026-11-29T18:00',
 'origin': '부산역',
 'destination': '부산역',
 'hotel': '페어필드 바이메리어트 부산송도비치',
 'turns': [[],
           [{'op': 'add', 'place': '송도해상케이블카', 'day': 1, 'at': '14:00'}],
           [{'op': 'add', 'place': '커피보이스 송도점', 'day': 1, 'after': '송도해상케이블카'}],
           [{'op': 'add', 'place': '흰여울문화마을', 'day': 2, 'at': '10:00', 'duration': 60}],
           [{'op': 'add', 'place': '올바릇식당 영도점', 'day': 2, 'at': '12:30', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '아르떼뮤지엄 부산', 'day': 2, 'after': '올바릇식당 영도점'}],
           [{'op': 'add', 'place': '자갈치시장', 'day': 3, 'at': '10:00', 'duration': 60}],
           [{'op': 'replace',
             'old': '올바릇식당 영도점',
             'place': '고향소갈비찜 자갈치점',
             'day': 2,
             'at': '12:30'}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(105, SPEC, turn_num, itinerary_id, request_status)
