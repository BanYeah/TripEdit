"""Registry of places. Place IDs accept numeric Kakao ids or their canonical URLs."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from app.hours import parse_hours
from app.models import Place

REQUIRED = {'place_id', 'name', 'latitude', 'longitude'}
KAKAO_ID = re.compile(r'^(?:https?://place\.map\.kakao\.com/)?([0-9]+)(?:/)?$')


def normalize_place_id(value: object) -> str:
    text = str(value or '').strip()
    match = KAKAO_ID.fullmatch(text)
    if match:
        return match.group(1)
    # Non-Kakao IDs are useful for local tests and example data.
    return text


def load_places(file: Path) -> dict[str, Place]:
    if not file.exists():
        raise FileNotFoundError(f'Places CSV not found: {file}')
    with file.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f'Places CSV missing columns: {sorted(missing)}')
        places: dict[str, Place] = {}
        for row_number, row in enumerate(reader, start=2):
            pid = normalize_place_id(row.get('place_id'))
            name = (row.get('name') or '').strip()
            if not pid or not name:
                raise ValueError(f'Line {row_number}: place_id and name are required')
            if pid in places:
                raise ValueError(f'Line {row_number}: duplicate place_id: {pid}')
            raw_lat = (row.get('latitude') or '').strip()
            raw_lon = (row.get('longitude') or '').strip()
            if bool(raw_lat) != bool(raw_lon):
                raise ValueError(f'Line {row_number}: both latitude and longitude are required together')
            lat = float(raw_lat) if raw_lat else None
            lon = float(raw_lon) if raw_lon else None
            if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f'Line {row_number}: coordinates out of range')
            minimum = int(float(row.get('min_duration') or 0)) if row.get('min_duration') else None
            if minimum is not None and minimum <= 0:
                raise ValueError(f'Line {row_number}: min_duration must be > 0')
            hours = parse_hours(row.get('opening_hours'))
            places[pid] = Place(
                place_id=pid,
                name=name,
                latitude=lat,
                longitude=lon,
                category=(row.get('category') or 'restaurant').strip(),
                opening_hours=hours,
                min_duration=minimum,
                place_url=(row.get('place_url') or f'https://place.map.kakao.com/{pid}' if pid.isdigit() else '').strip(),
            )
    return places
