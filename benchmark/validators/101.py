# Generated turn-level scenario expectations matching 101.txt.
from ._scenario_common import validate_scenario

SPEC = {'start': '2026-11-23T10:00',
 'end': '2026-11-25T18:00',
 'origin': '부산역',
 'destination': '부산역',
 'hotel': '스탠포드호텔 부산',
 'turns': [[],
           [{'op': 'add', 'place': '이재모피자 본점', 'day': 1, 'at': '12:30', 'meal': 'lunch'}],
           [{'op': 'add', 'place': '부산타워', 'day': 1, 'at': '15:00'}],
           [{'op': 'replace', 'old': '이재모피자 본점', 'place': '톤쇼우 남포점', 'day': 1, 'at': '12:30'}],
           [{'op': 'add', 'place': '감천문화마을', 'day': 2, 'at': '10:00', 'duration': 90}],
           [{'op': 'add', 'place': '커피보이스 송도점', 'day': 2, 'after': '감천문화마을'}],
           [{'op': 'move', 'place': '부산타워', 'day': 1, 'at': '17:00'}],
           [{'op': 'remove', 'place': '커피보이스 송도점', 'day': 2}]]}

def validator(turn_num, itinerary_id, request_status):
    return validate_scenario(101, SPEC, turn_num, itinerary_id, request_status)
