import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings
from app.models import Mode, Route

HOURS_A = {x: [['11:00', '15:00'], ['17:00', '20:00']] for x in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')}
HOURS_B = {x: [['11:00', '20:00']] for x in ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')}


class FakeEngine:
    def __init__(self):
        self.calls = []
    async def available(self):
        return True
    async def route(self, origin, destination, mode, departure):
        self.calls.append((origin.place_id, destination.place_id, mode, departure))
        return Route(37*60000, 12000.0, 1 if mode == Mode.TRANSIT else None)


def make_app(tmp_path: Path):
    path = tmp_path / 'places.csv'
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, ['place_id','name','latitude','longitude','category','opening_hours','min_duration'])
        w.writeheader()
        w.writerow({'place_id':'10','name':'식당 A','latitude':35.12,'longitude':129.01,'category':'restaurant', 'opening_hours':json.dumps(HOURS_A), 'min_duration':40})
        w.writerow({'place_id':'20','name':'식당 B','latitude':35.15,'longitude':129.04,'category':'restaurant','opening_hours':json.dumps(HOURS_B),'min_duration':60})
    settings=Settings('http://fake','schedule-tests',path,tmp_path/'cache.sqlite3',10,3600,3600,1)
    engine=FakeEngine()
    return create_app(settings,engine), engine


def input_plan(dinner_time='18:00', lunch_time='12:00'):
    return {'visits':[
        {'visit_id':'lunch','place_id':'10','start_at':f'2026-11-10T{lunch_time}:00+09:00', 'mode_from_previous':'WALK'},
        {'visit_id':'dinner','place_id':'https://place.map.kakao.com/20','start_at':f'2026-11-10T{dinner_time}:00+09:00', 'mode_from_previous':'TRANSIT'},
    ]}


def test_valid_plan_routes_and_persistent_save(tmp_path):
    app, engine=make_app(tmp_path)
    with TestClient(app) as c:
        result=c.post('/itineraries/validate',json=input_plan())
        assert result.status_code==200,result.text
        data=result.json()
        assert data['valid'] is True
        assert data['travel_legs'][0]['required_minutes']==37
        assert engine.calls[0][2]==Mode.TRANSIT
        saved=c.put('/itineraries/day1',json=input_plan())
        assert saved.status_code==200,saved.text
        assert saved.json()['saved'] is True
        fetched=c.get('/itineraries/day1')
        assert fetched.status_code==200
        assert len(fetched.json()['visits'])==2
        assert len(engine.calls)==1 # cache was shared between plan and route API
        changed=input_plan(dinner_time='19:00')
        reject=c.put('/itineraries/day1',json=changed)
        assert reject.status_code==409
        assert any(x['code']=='preserve_existing' for x in reject.json()['detail']['errors'])
        changed['allowed_change_visit_ids']=['dinner']
        assert c.put('/itineraries/day1',json=changed).status_code==200


def test_closed_brake_window_invalid_and_short_travel(tmp_path):
    app, engine=make_app(tmp_path)
    with TestClient(app) as c:
        bad=input_plan(lunch_time='15:10')
        result=c.post('/itineraries/validate',json=bad).json()
        codes={x['code'] for x in result['errors']}
        assert 'restaurant_meal_window' in codes
        assert 'outside_opening_hours' in codes
        two_at_lunch=input_plan(dinner_time='12:45')
        result2=c.post('/itineraries/validate',json=two_at_lunch).json()
        codes2={x['code'] for x in result2['errors']}
        assert 'duplicate_meal' in codes2
        assert 'insufficient_travel_time' in codes2


def test_missing_coords_do_not_fake_travel(tmp_path):
    app,engine=make_app(tmp_path)
    # Non-existent place must produce report error, not success.
    plan=input_plan()
    plan['visits'][1]['place_id']='NOT_KAKAO'
    with TestClient(app) as c:
        result=c.post('/itineraries/validate',json=plan).json()
        assert result['valid'] is False
        assert any(x['code']=='unknown_place' for x in result['errors'])


def test_explicit_multiturn_edit_keeps_original_on_failure(tmp_path):
    app, engine=make_app(tmp_path)
    with TestClient(app) as c:
        initial={'visits':[input_plan()['visits'][0]]}
        assert c.put('/itineraries/trip',json=initial).status_code==200
        add={
            'action':'add','visit_id':'dinner','place_id':'20',
            'start_at':'2026-11-10T18:00:00+09:00','mode_from_previous':'TRANSIT',
        }
        assert c.post('/itineraries/trip/edit',json=add).status_code==200
        move={'action':'move','visit_id':'dinner','start_at':'2026-11-10T12:45:00+09:00'}
        r=c.post('/itineraries/trip/edit',json=move)
        assert r.status_code==409
        assert any(i['code']=='insufficient_travel_time' for i in r.json()['detail']['errors'])
        assert c.get('/itineraries/trip').json()['visits'][1]['start_at'].startswith('2026-11-10T18:00:00')
        delete={'action':'delete','visit_id':'dinner'}
        assert c.post('/itineraries/trip/edit',json=delete).status_code==200
        assert len(c.get('/itineraries/trip').json()['visits'])==1


def test_missing_timezone_report_not_server_error(tmp_path):
    app,_=make_app(tmp_path)
    with TestClient(app) as c:
        plan=input_plan()
        plan['visits'][0]['start_at']='2026-11-10T12:00:00'
        resp=c.post('/itineraries/validate',json=plan)
        assert resp.status_code==200
        assert resp.json()['valid'] is False
        assert any(x['code']=='timezone_required' for x in resp.json()['errors'])
