import csv
import json
from pathlib import Path

from app.hours import is_open_for, parse_hours
from app.places import load_places, normalize_place_id
from app.workbook import read_sheet
from scripts.import_restaurants import import_restaurants
from datetime import datetime


def test_real_workbook_restaurant_only_and_json(tmp_path):
    src = Path('data/TripEdit-Places.xlsx')
    rows = read_sheet(src, 'restaurant')
    assert len(rows) == 50
    assert all(parse_hours(r['opening_hours']) for r in rows)
    assert all(not r['latitude'] and not r['longitude'] for r in rows)
    out = tmp_path / 'out.csv'
    result = import_restaurants(src, out)
    assert result['restaurant_count'] == 50
    assert result['routable_count'] == 0
    places = load_places(out)
    assert len(places) == 50
    assert all(p.min_duration and p.opening_hours and p.category == 'restaurant' for p in places.values())
    assert all(not p.routable for p in places.values())
    assert normalize_place_id('https://place.map.kakao.com/25505923') == '25505923'


def test_existing_kakao_verified_coordinates_survive_reimport(tmp_path):
    src = Path('data/TripEdit-Places.xlsx')
    out = tmp_path / 'places.csv'
    import_restaurants(src, out)
    with out.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    pid = rows[0]['place_id']
    rows[0]['latitude'] = '35.12345678'
    rows[0]['longitude'] = '129.01234567'
    rows[0]['coord_source'] = 'kakao_local_exact_id'
    with out.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    res = import_restaurants(src, out)
    assert res['routable_count'] == 1
    place = load_places(out)[pid]
    assert place.latitude == 35.12345678
    assert place.longitude == 129.01234567


def test_break_time_closed_day_and_overnight():
    hours = parse_hours('{"mon":[["11:00","15:00"],["17:00","21:00"]],"tue":[],"wed":[],"thu":[],"fri":[],"sat":[],"sun":[["22:00","02:00"]]}')
    assert is_open_for(hours, datetime.fromisoformat('2026-11-09T11:30:00+09:00'), 45)
    assert not is_open_for(hours, datetime.fromisoformat('2026-11-09T15:10:00+09:00'), 30)
    assert not is_open_for(hours, datetime.fromisoformat('2026-11-10T12:00:00+09:00'), 30)
    assert is_open_for(hours, datetime.fromisoformat('2026-11-09T00:30:00+09:00'), 60)
