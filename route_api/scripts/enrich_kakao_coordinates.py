"""Fill only verified Kakao coordinates in data/places.csv.

Kakao REST API key must be set outside source code. Does not infer hours.
Never overwrites existing coordinates unless --force is passed.
Unmatched IDs are reported and left blank, without guessing.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

from app.kakao_local import KakaoLocalSearch


def save_rows(path: Path, rows: list[dict]) -> None:
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def run(csv_path: Path, search: KakaoLocalSearch, *, limit: int = 0, force: bool = False, delay: float = 0.25) -> dict:
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    count, unmatched, attempted = 0, [], 0
    for row in rows:
        if row.get('latitude') and row.get('longitude') and not force:
            continue
        if limit and attempted >= limit:
            break
        attempted += 1
        loc = search.find_exact_id(row['place_id'], row['name'])
        if loc is None:
            unmatched.append({'place_id': row['place_id'], 'name': row['name'], 'place_url': row.get('place_url')})
            print(f'NOT_FOUND {row["place_id"]} {row["name"]}')
        else:
            row['latitude'] = f'{loc.latitude:.8f}'
            row['longitude'] = f'{loc.longitude:.8f}'
            row['coord_source'] = 'kakao_local_exact_id'
            count += 1
            save_rows(csv_path, rows)  # Save good results before a quota interruption.
            print(f'MATCHED {row["place_id"]} {row["name"]} ({loc.latitude:.6f}, {loc.longitude:.6f})')
        if delay:
            time.sleep(delay)
    report = {'attempted': attempted, 'new_coordinates': count, 'unmatched': unmatched,
              'remaining_missing': sum(not (r.get('latitude') and r.get('longitude')) for r in rows)}
    csv_path.with_name('coordinate_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--csv', type=Path, default=Path('data/places.csv'))
    p.add_argument('--limit', type=int, default=0, help='0=all; try 2 first')
    p.add_argument('--force', action='store_true')
    p.add_argument('--delay', type=float, default=0.25)
    args = p.parse_args()
    if args.limit < 0 or args.delay < 0:
        p.error('--limit and --delay must be >= 0')
    key = os.getenv('KAKAO_REST_API_KEY')
    if not key:
        p.error('Set KAKAO_REST_API_KEY (Kakao Developers REST API key) first')
    print(json.dumps(run(args.csv, KakaoLocalSearch(key), limit=args.limit, force=args.force, delay=args.delay), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
