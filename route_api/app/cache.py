"""Simple durable SQLite cache; invalidated by data_version and coordinates."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from app.models import Route


class SqliteRouteCache:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""
                CREATE TABLE IF NOT EXISTS routes (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
            """)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def get(self, key: str, ttl_seconds: int) -> Route | None:
        with self._connect() as c:
            found = c.execute("SELECT data, created_at FROM routes WHERE key=?", (key,)).fetchone()
            if not found or time.time() - found[1] >= ttl_seconds:
                return None
            payload = json.loads(found[0])
            return Route(**payload)

    def put(self, key: str, route: Route) -> None:
        payload = json.dumps(route.__dict__, separators=(",", ":"))
        with self._connect() as c:
            c.execute(
                "INSERT OR REPLACE INTO routes(key,data,created_at) VALUES(?,?,?)",
                (key, payload, int(time.time())),
            )
