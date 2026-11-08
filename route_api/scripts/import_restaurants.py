"""Import exactly the restaurant tab from TripEdit-Places.xlsx into places.csv.

No maps/geocoding and no fabricated hours. Existing coordinates from a prior
verified places.csv survive imports unless source workbook provides coordinates.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.hours import parse_hours
from app.workbook import read_sheet
from app.places import normalize_place_id

COLUMNS = ('place_id', 'name', 'category', 'latitude', 'longitude', 'opening_hours', 'min_duration', 'place_url', 'coord_source')


def import_restaurants(xlsx: Path, output: Path, *, preserve_coordinates: bool = True) -> dict:
    items = read_sheet(xlsx, 'restaurant')
    existing: dict[str, dict] = {}
    if preserve_coordinates and output.exists():
        with output.open('r', encoding='utf-8-sig', newline='') as f:
            existing = {row['place_id']: row for row in csv.DictReader(f)}
    rows, seen = [], set()
    for row in items:
        pid = normalize_place_id(row.get('place_id', ''))
        name = (row.get('name') or '').strip()
        if not pid or not name:
            raise ValueError('restaurant has blank place_id/name')
        if pid in seen:
            raise ValueError(f'Duplicate restaurant place_id: {pid}')
        seen.add(pid)
        raw_hours = (row.get('opening_hours') or '').strip()
        if not raw_hours:
            raise ValueError(f'{name}: opening_hours is missing')
        parse_hours(raw_hours)
        min_duration = int(float(row.get('min_duration') or 0))
        if min_duration <= 0:
            raise ValueError(f'{name}: min_duration must be > 0')
        old = existing.get(pid, {})
        lat = (row.get('latitude') or '').strip()
        lon = (row.get('longitude') or '').strip()
        if bool(lat) != bool(lon):
            raise ValueError(f'{name}: partial coordinate')
        if not lat and not lon:
            lat = old.get('latitude', '')
            lon = old.get('longitude', '')
        source = 'xlsx' if row.get('latitude') and row.get('longitude') else old.get('coord_source', '')
        rows.append({
            'place_id': pid, 'name': name, 'category': 'restaurant',
            'latitude': lat, 'longitude': lon,
            'opening_hours': raw_hours, 'min_duration': str(min_duration),
            'place_url': f'https://place.map.kakao.com/{pid}',
            'coord_source': source,
        })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    summary = {'restaurant_count': len(rows), 'routable_count': sum(bool(x['latitude']) and bool(x['longitude']) for x in rows), 'output': str(output)}
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--xlsx', type=Path, default=Path('data/TripEdit-Places.xlsx'))
    p.add_argument('--output', type=Path, default=Path('data/places.csv'))
    p.add_argument('--reset-coordinates', action='store_true', help='Do not preserve previously validated coordinates')
    args = p.parse_args()
    print(json.dumps(import_restaurants(args.xlsx, args.output, preserve_coordinates=not args.reset_coordinates), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
