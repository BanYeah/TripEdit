"""Does a static GTFS feed contain service for the requested YYYY-MM-DD?

Structural/calendar check only; live delays and real-world accuracy are separate.
Does not approximate missing scheduled routes.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from datetime import date
from pathlib import Path
from zipfile import ZipFile


DAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')


def check_day(archive: Path, requested: date) -> dict:
    with ZipFile(archive) as z:
        files = {Path(n).name: n for n in z.namelist() if not n.endswith('/')}
        def records(name: str):
            if name not in files:
                return
            with z.open(files[name]) as src:
                yield from csv.DictReader(io.TextIOWrapper(src, encoding='utf-8-sig', newline=''))
        active = set()
        day_string = requested.strftime('%Y%m%d')
        for row in records('calendar.txt'):
            if row.get('start_date', '') <= day_string <= row.get('end_date', '') and row.get(DAYS[requested.weekday()]) == '1':
                active.add(row['service_id'])
        for row in records('calendar_dates.txt'):
            if row.get('date') == day_string:
                if row.get('exception_type') == '1':
                    active.add(row['service_id'])
                if row.get('exception_type') == '2':
                    active.discard(row['service_id'])
        trips = sum(1 for row in records('trips.txt') if row.get('service_id') in active)
        return {'date': requested.isoformat(), 'active_service_count': len(active), 'scheduled_trips': trips,
                'date_covered': trips > 0, 'note': 'A feed-level calendar check, not a guarantee of routes for Busan or any two places.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('gtfs_zip', type=Path)
    p.add_argument('--date', required=True, type=date.fromisoformat)
    args = p.parse_args()
    result = check_day(args.gtfs_zip, args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result['date_covered']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
