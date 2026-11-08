"""Check which stages are locally ready; avoids ambiguous success claims."""
from __future__ import annotations
import json
from pathlib import Path
import httpx
from app.places import load_places
from scripts.validate_gtfs import inspect_gtfs


def main():
    path = Path('data/places.csv')
    places = load_places(path) if path.exists() else {}
    osm = Path('data/engine/busan.osm.pbf')
    gtfs = Path('data/engine/busan.gtfs.zip')
    engine = {}
    try:
        response = httpx.get('http://127.0.0.1:8989/info', timeout=2)
        if response.is_success:
            engine = response.json()
    except httpx.HTTPError:
        pass
    profiles = engine.get('profiles', [])
    names = [x.get('name') for x in profiles if isinstance(x, dict)]
    summary = {
        'restaurant_records': len(places),
        'coordinates_ready': sum(p.routable for p in places.values()),
        'osm_file_present': osm.is_file() and osm.stat().st_size > 0,
        'gtfs_file_present': gtfs.is_file() and gtfs.stat().st_size > 0,
        'graphhopper_server_reachable': bool(engine),
        'available_profiles': names,
        'walking_engine_maybe_ready': 'foot' in names,
        'transit_engine_maybe_ready': 'pt' in names,
    }
    if gtfs.is_file():
        try:
            summary['gtfs_summary'] = inspect_gtfs(gtfs)
        except Exception as e:
            summary['gtfs_error'] = str(e)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
