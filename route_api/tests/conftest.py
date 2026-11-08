from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.main import create_app
from app.models import Mode, Route


class FakeEngine:
    def __init__(self):
        self.calls = []

    async def available(self):
        return True

    async def route(self, origin, destination, mode, departure):
        self.calls.append((origin, destination, mode, departure))
        if mode == Mode.TRANSIT:
            return Route(duration_ms=36 * 60_000 + 1000, distance_meters=17890.0, transfer_count=1)
        return Route(duration_ms=8 * 60_000 + 1, distance_meters=530.2, transfer_count=None)


@pytest.fixture
def test_context(tmp_path: Path):
    csv = tmp_path / "places.csv"
    csv.write_text(
        "place_id,name,latitude,longitude\n"
        "101,테스트 A,35.153,129.119\n"
        "102,테스트 B,35.115,129.040\n"
        "103,좌표 없음,,\n",
        encoding="utf-8-sig",
    )
    settings = Settings(
        graph_hopper_url="http://gh.test",
        data_version="test-graph-1",
        places_csv=csv,
        cache_db=tmp_path / "cache.sqlite3",
        http_timeout_seconds=5,
        walk_cache_ttl_seconds=6000,
        transit_cache_ttl_seconds=6000,
        transit_bucket_minutes=1,
    )
    engine = FakeEngine()
    return create_app(settings, engine), engine
