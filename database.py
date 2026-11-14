import csv
import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "db.sqlite3"
TRAVEL_TIME_PATH = Path(__file__).resolve().parent / "dataset" / "travel-time.csv"

SCHEMA = """
CREATE TABLE IF NOT EXISTS travel_times (
    origin_id INTEGER NOT NULL,
    origin_name TEXT NOT NULL,
    destination_id INTEGER NOT NULL,
    destination_name TEXT NOT NULL,

    walk_status TEXT NOT NULL,
    walk_minutes INTEGER CHECK (walk_minutes >= 0),
    transit_status TEXT NOT NULL,
    transit_minutes INTEGER CHECK (transit_minutes >= 0),

    PRIMARY KEY (origin_id, destination_id)
);

CREATE TABLE IF NOT EXISTS itineraries (
    itinerary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,

    CHECK (start_time < end_time)
);

CREATE TABLE IF NOT EXISTS segments (
    segment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_type TEXT NOT NULL CHECK (segment_type IN ('STOP', 'LEG')),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,

    place_id INTEGER,
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
            load_travel_times(connection)
    finally:
        connection.close()


def load_travel_times(connection: sqlite3.Connection) -> None:
    with TRAVEL_TIME_PATH.open(encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        connection.execute("DELETE FROM travel_times")
        connection.executemany(
            """INSERT INTO travel_times
               (origin_id, origin_name, destination_id, destination_name,
                walk_status, walk_minutes, transit_status, transit_minutes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                (
                    int(row["origin_id"]), row["origin_name"],
                    int(row["destination_id"]), row["destination_name"],
                    row["walk_status"],
                    int(row["walk_minutes"]) if row["walk_minutes"] else None,
                    row["transit_status"],
                    int(row["transit_minutes"]) if row["transit_minutes"] else None,
                )
                for row in rows
            ),
        )


def get_database():
    connection = connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()
