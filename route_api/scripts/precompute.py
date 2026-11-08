#!/usr/bin/env python3
"""Explicit offline pairwise precomputation using the running TripEdit API."""
from __future__ import annotations

import argparse
import asyncio
import csv
from itertools import permutations
from pathlib import Path

import httpx

from app.places import load_places


async def precompute(args):
    places = [p for p in load_places(Path(args.places)).values() if p.routable]
    if len(places) < 2:
        raise ValueError("At least two places with verified coordinates are needed")
    if "TRANSIT" in args.modes and not args.departure:
        raise ValueError("TRANSIT requires --departure timezone-aware ISO timestamp")
    work = []
    for origin, dest in permutations(places, 2):
        for mode in args.modes:
            work.append((origin, dest, mode))
    print(f"{len(places)} routable places; {len(work)} queries (direction matters)")
    if not args.yes:
        print("Dry run only. Add --yes to send queries and write CSV.")
        return
    sem = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        async def single(origin, dest, mode):
            async with sem:
                params = {"from_id": origin.place_id, "to_id": dest.place_id, "mode": mode}
                if mode == "TRANSIT":
                    params["departure"] = args.departure
                try:
                    response = await client.get(args.base_url.rstrip("/") + "/travel-time", params=params)
                    payload = response.json()
                    if response.status_code != 200:
                        return (origin.place_id, dest.place_id, mode, "", response.status_code, str(payload)[:240])
                    return (origin.place_id, dest.place_id, mode, payload["duration_minutes"], 200, "")
                except httpx.HTTPError as exc:
                    return (origin.place_id, dest.place_id, mode, "", "ERR", str(exc)[:240])
        results = await asyncio.gather(*(single(o, d, m) for o, d, m in work))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["from_id", "to_id", "mode", "duration_minutes", "http_status", "error"])
        w.writerows(results)
    successes = sum(r[4] == 200 for r in results)
    print(f"Wrote {output} successes={successes} failed={len(results)-successes}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--places", default="data/places.csv")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--modes", nargs="+", choices=["WALK", "TRANSIT"], default=["WALK"])
    p.add_argument("--departure", help="ISO-8601 with timezone, e.g. 2026-11-09T10:00:00+09:00")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--timeout", type=float, default=45)
    p.add_argument("--output", default="data/matrix.csv")
    p.add_argument("--yes", action="store_true", help="Actually call the API")
    args = p.parse_args()
    if args.concurrency < 1 or args.concurrency > 50:
        p.error("--concurrency must be 1 to 50")
    asyncio.run(precompute(args))


if __name__ == "__main__":
    main()
