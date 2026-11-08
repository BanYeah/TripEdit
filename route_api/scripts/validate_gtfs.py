#!/usr/bin/env python3
"""Basic structural validation; not a substitute for GTFS Validator or local schedule audit."""
from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path


def inspect_gtfs(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        names = {Path(n).name: n for n in z.namelist() if not n.endswith("/")}
        required = {"agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
        missing = required - names.keys()
        if missing:
            raise ValueError(f"Missing GTFS files: {', '.join(sorted(missing))}")
        if not ({"calendar.txt", "calendar_dates.txt"} & names.keys()):
            raise ValueError("Missing service calendar (calendar.txt or calendar_dates.txt)")
        def scan(filename: str, *, take: int = 0):
            if filename not in names:
                return 0, []
            with z.open(names[filename]) as b:
                text = io.TextIOWrapper(b, encoding="utf-8-sig", newline="")
                reader = csv.DictReader(text)
                sampled = []
                count = 0
                for row in reader:
                    count += 1
                    if take and len(sampled) < take:
                        sampled.append(row)
                return count, sampled
        agency_count, agencies = scan("agency.txt", take=1000)
        timezone_values = sorted({r.get("agency_timezone", "").strip() for r in agencies})
        if any(tz in ("Korea", "", "ROK") for tz in timezone_values):
            raise ValueError(f"Unsupported agency_timezone: {timezone_values}; use Asia/Seoul")
        stops_count, _ = scan("stops.txt")
        routes_count, _ = scan("routes.txt")
        trips_count, _ = scan("trips.txt")
        stop_times_count, _ = scan("stop_times.txt")
        cal_count, calendar = scan("calendar.txt", take=10000)
        exc_count, exception_days = scan("calendar_dates.txt", take=10000)
        starts = sorted(r.get("start_date", "") for r in calendar if r.get("start_date"))
        ends = sorted(r.get("end_date", "") for r in calendar if r.get("end_date"))
        exception_dates = sorted(r.get("date", "") for r in exception_days if r.get("date"))
        all_dates = starts + exception_dates
        all_ends = ends + exception_dates
        return {
            "agencies": agency_count,
            "stops": stops_count,
            "routes": routes_count,
            "trips": trips_count,
            "stop_times": stop_times_count,
            "calendar_records": cal_count,
            "exception_records": exc_count,
            "timezones": timezone_values,
            "observed_start_date": min(all_dates) if all_dates else None,
            "observed_end_date": max(all_ends) if all_ends else None,
            "saturday_calendar_services": sum(r.get("saturday") == "1" for r in calendar),
            "sunday_calendar_services": sum(r.get("sunday") == "1" for r in calendar),
            "warning": "Check that requested dates and weekend service really exist; pilot feed may be weekday-only.",
        }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("gtfs_zip", type=Path)
    args = p.parse_args()
    for k, v in inspect_gtfs(args.gtfs_zip).items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
