#!/usr/bin/env python3
"""Show why a dataset is / isn't routable, without inventing coordinates."""
from __future__ import annotations

import argparse
from pathlib import Path

from app.places import load_places


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/places.csv")
    args = parser.parse_args()
    places = load_places(Path(args.csv))
    with_coords = [p for p in places.values() if p.routable]
    missing = [p for p in places.values() if not p.routable]
    print(f"total={len(places)} routable={len(with_coords)} missing_coordinates={len(missing)}")
    for p in missing[:15]:
        print(f"NEEDS_COORDINATES {p.place_id} {p.name}")
    if missing:
        print("Add latitude,longitude for every route candidate; Kakao place ID alone is not enough.")


if __name__ == "__main__":
    main()
