import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "db.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS itineraries (
    itinerary_id INTEGER PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,

    CHECK (start_time < end_time)
);

CREATE TABLE IF NOT EXISTS segments (
    segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_type TEXT NOT NULL CHECK (segment_type IN ('STOP', 'LEG')),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,

    place_id TEXT,
    place_name TEXT,
    place_category TEXT,
    
    transport_mode TEXT CHECK (transport_mode IN ('WALK', 'TRANSIT')),

    itinerary_id INTEGER NOT NULL,
    FOREIGN KEY (itinerary_id) REFERENCES itineraries(itinerary_id) ON DELETE CASCADE,

    CHECK (start_time < end_time),
    CHECK (
        (segment_type = 'STOP' AND place_id IS NOT NULL AND transport_mode IS NULL)
        OR
        (segment_type = 'LEG' AND place_id IS NULL AND transport_mode IS NOT NULL)
    )
);
"""


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = connect()
    try:
        with connection:
            connection.executescript(SCHEMA)
    finally:
        connection.close()


def get_database():
    connection = connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()
