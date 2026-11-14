import os
import hashlib
from pathlib import Path

import csv
import json
import fcntl
import zipfile
import tempfile

BASE = Path(__file__).resolve().parent
SOURCE = BASE.parent / "dataset" / "gtfs"
DATA = BASE / "data"
REQUIRED = {"agency.txt", "trips.txt", "routes.txt", "stops.txt", "stop_times.txt"}


def prepare():
    DATA.mkdir(exist_ok=True)
    with (DATA / ".prepare.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        files = sorted(SOURCE.glob("*.txt"))
        missing = REQUIRED - {p.name for p in files}
        if missing or not any((SOURCE / name).is_file() for name in ("calendar.txt", "calendar_dates.txt")):
            raise SystemExit(f"GTFS 필수 파일을 확인하세요: {sorted(missing)}, calendar.txt 또는 calendar_dates.txt 필요")
        
        if not (BASE.parent / "dataset/osm/korea.osm.pbf").is_file():
            raise SystemExit("dataset/osm/korea.osm.pbf 파일이 필요합니다.")
        
        fingerprint = hashlib.sha256(json.dumps(
            [(p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in files]
        ).encode()).hexdigest()
        output = DATA / "korea-gtfs.zip"
        stamp = DATA / "gtfs-manifest.json"
        if output.exists() and stamp.exists() and json.loads(stamp.read_text())["fingerprint"] == fingerprint:
            print("GTFS 준비 완료 (기존 압축 사용)", flush=True)
            return
        if (DATA / "graph").exists():
            raise SystemExit("GTFS가 변경되었습니다. 서버 종료 후 data/graph를 별도 경로로 옮기고 다시 준비하세요.")
        
        print("GTFS 압축 중 (대용량 stop_times는 스트리밍 처리)...", flush=True)
        fd, name = tempfile.mkstemp(dir=DATA, suffix=".zip.tmp")
        os.close(fd)
        try:
            with zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
                for path in files:
                    if path.name == "agency.txt":
                        with path.open(encoding="utf-8-sig", newline="") as source:
                            rows = list(csv.DictReader(source))
                        import io
                        stream = io.StringIO(newline="")
                        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                        writer.writeheader()
                        for row in rows:
                            if row["agency_timezone"] == "Korea":
                                row["agency_timezone"] = "Asia/Seoul"
                            writer.writerow(row)
                        archive.writestr(path.name, stream.getvalue().encode("utf-8"))
                    else:
                        archive.write(path, path.name)
            os.replace(name, output)
            stamp.write_text(json.dumps({"fingerprint": fingerprint, "source": str(SOURCE)}, indent=2))
        finally:
            Path(name).unlink(missing_ok=True)
        print(f"GTFS 준비 완료: {output}", flush=True)


if __name__ == "__main__":
    prepare()
