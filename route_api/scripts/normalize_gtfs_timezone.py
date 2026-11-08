#!/usr/bin/env python3
"""Write a NEW GTFS zip replacing obsolete agency timezone 'Korea' with 'Asia/Seoul'."""
from __future__ import annotations

import argparse
import csv
import io
import zipfile
from pathlib import Path


def normalize(src: Path, dest: Path) -> int:
    if src.resolve() == dest.resolve():
        raise ValueError("Input and output paths must differ")
    replaced = 0
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dest, "w") as zout:
        for member in zin.infolist():
            raw = zin.read(member.filename)
            if Path(member.filename).name == "agency.txt":
                text = io.StringIO(raw.decode("utf-8-sig"), newline="")
                rows = list(csv.DictReader(text))
                columns = list(rows[0]) if rows else []
                for row in rows:
                    if row.get("agency_timezone") == "Korea":
                        row["agency_timezone"] = "Asia/Seoul"
                        replaced += 1
                out = io.StringIO(newline="")
                writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
                raw = out.getvalue().encode("utf-8")
            zout.writestr(member, raw)
    return replaced


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src", type=Path)
    p.add_argument("dest", type=Path)
    args = p.parse_args()
    count = normalize(args.src, args.dest)
    print(f"Created {args.dest}; changed {count} agency_timezone records")


if __name__ == "__main__":
    main()
