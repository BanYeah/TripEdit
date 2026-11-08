from __future__ import annotations

import csv
import io
import zipfile

import pytest

from app.places import load_places
from scripts.normalize_gtfs_timezone import normalize
from scripts.validate_gtfs import inspect_gtfs


def test_duplicate_id_and_partial_coordinate_rejected(tmp_path):
    target = tmp_path / "x.csv"
    target.write_text("place_id,name,latitude,longitude\nA,X,35.1,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="both latitude"):
        load_places(target)
    target.write_text("place_id,name,latitude,longitude\nA,X,35.1,129.1\nA,Y,35.2,129.2\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_places(target)


def test_gtfs_rewrite_and_validation(tmp_path):
    src = tmp_path / "source.zip"
    dst = tmp_path / "normalized.zip"
    csvs = {
        "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\nA1,KTDB,https://www.ktdb.go.kr,Korea\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\nS1,Stop,35.1,129.1\n",
        "routes.txt": "route_id,agency_id,route_short_name,route_type\nR1,A1,1,3\n",
        "trips.txt": "route_id,service_id,trip_id\nR1,WK,T1\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nT1,09:00:00,09:00:00,S1,1\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nWK,1,1,1,1,1,0,0,20250101,20251231\n",
    }
    with zipfile.ZipFile(src, "w") as archive:
        for name, content in csvs.items():
            archive.writestr(name, content)
    with pytest.raises(ValueError, match="timezone"):
        inspect_gtfs(src)
    assert normalize(src, dst) == 1
    summary = inspect_gtfs(dst)
    assert summary["agencies"] == 1
    assert summary["stop_times"] == 1
    assert summary["observed_end_date"] == "20251231"
    assert summary["sunday_calendar_services"] == 0
