"""Runtime configuration. All paths stay local to this project."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_from_env(name: str, default: int) -> int:
    result = int(os.getenv(name, str(default)))
    if result <= 0:
        raise ValueError(f"{name} must be > 0")
    return result


@dataclass(frozen=True)
class Settings:
    graph_hopper_url: str
    data_version: str
    places_csv: Path
    cache_db: Path
    http_timeout_seconds: float
    walk_cache_ttl_seconds: int
    transit_cache_ttl_seconds: int
    transit_bucket_minutes: int

    @classmethod
    def from_env(cls) -> "Settings":
        bucket = _int_from_env("TRANSIT_BUCKET_MINUTES", 1)
        if 60 % bucket != 0:
            raise ValueError("TRANSIT_BUCKET_MINUTES must evenly divide 60")
        return cls(
            graph_hopper_url=os.getenv("GRAPH_HOPPER_URL", "http://127.0.0.1:8989").rstrip("/"),
            data_version=os.getenv("DATA_VERSION", "busan-initial-001"),
            places_csv=Path(os.getenv("PLACES_CSV", "data/places.csv")),
            cache_db=Path(os.getenv("CACHE_DB", "data/route_cache.sqlite3")),
            http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
            walk_cache_ttl_seconds=_int_from_env("WALK_CACHE_TTL_SECONDS", 604800),
            transit_cache_ttl_seconds=_int_from_env("TRANSIT_CACHE_TTL_SECONDS", 86400),
            transit_bucket_minutes=bucket,
        )
