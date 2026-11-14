import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from database import get_database

router = APIRouter(prefix="/travel-time", tags=["travel-time"])


class TravelTime(BaseModel):
    origin_id: int
    origin_name: str
    destination_id: int
    destination_name: str
    walk_status: str
    walk_minutes: int | None = Field(description="Walking duration in minutes, if available")
    transit_status: str
    transit_minutes: int | None = Field(description="Public transit duration in minutes, if available")


@router.get("/{origin_id}/{destination_id}", response_model=TravelTime)
def get_travel_time(
    origin_id: int,
    destination_id: int,
    database: Annotated[sqlite3.Connection, Depends(get_database)],
) -> TravelTime:
    """Retrieve travel times for a directed origin/destination pair."""
    row = database.execute(
        """SELECT origin_id, origin_name, destination_id, destination_name,
                  walk_status, walk_minutes, transit_status, transit_minutes
           FROM travel_times WHERE origin_id = ? AND destination_id = ?""",
        (origin_id, destination_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Travel time not found")
    return TravelTime(**dict(row))
