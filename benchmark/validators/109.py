# Generated turn-level scenario expectations matching 109.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-12-03T09:00',
 'end': '2026-12-07T19:00',
 'origin': '부산역',
 'destination': '부산역',
 'hotel': '스탠포드호텔 부산',
 'turns': [[],
           [{'op': 'add', 'place': '이재모피자 본점', 'day': 1, 'at': '12:30', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '톤쇼우 남포점', 'day': 2, 'at': '12:30', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '본전돼지국밥', 'day': 3, 'at': '12:30', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '신발원', 'day': 4, 'at': '12:30', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '고향소갈비찜 자갈치점', 'day': 5, 'at': '12:30', 'meal': 'lunch'}],
           [{'op': 'reject'}],
           [{'op': 'replace', 'old': '신발원', 'place': '남천가야밀면', 'day': 4, 'at': '12:30'}],
           [{'op': 'add', 'place': '감천문화마을', 'day': 3, 'at': '10:00'}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(109, SPEC, turn_num, itinerary_id, request_status)
