#!/usr/bin/env python3
"""Query the REAL GraphHopper engine; unlike unit tests this needs OSM/GTFS running."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from app.graphhopper import GraphHopperClient
from app.models import Mode, Place


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8989")
    parser.add_argument("--from-lat", type=float, required=True)
    parser.add_argument("--from-lon", type=float, required=True)
    parser.add_argument("--to-lat", type=float, required=True)
    parser.add_argument("--to-lon", type=float, required=True)
    parser.add_argument("--mode", choices=["WALK", "TRANSIT"], default="WALK")
    parser.add_argument("--departure", help="ISO-8601 with timezone required for TRANSIT")
    args = parser.parse_args()
    mode = Mode(args.mode)
    departure = datetime.fromisoformat(args.departure) if args.departure else None
    if mode is Mode.TRANSIT and not departure:
        parser.error("TRANSIT requires --departure")
    client = GraphHopperClient(args.base_url)
    print("GraphHopper server visible:", await client.available())
    first = Place("TEST_A", "test A", args.from_lat, args.from_lon)
    second = Place("TEST_B", "test B", args.to_lat, args.to_lon)
    route = await client.route(first, second, mode, departure)
    print(f"duration={route.duration_ms/60000:.2f} min distance={route.distance_meters}m transfers={route.transfer_count}")
    print("NOTE: This demonstrates reachability only; validate against trusted Busan routes before benchmark use.")


if __name__ == "__main__":
    asyncio.run(main())
