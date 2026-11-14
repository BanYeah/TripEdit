import sqlite3
from typing import Annotated, Literal, Self

from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator

from database import get_database
from .place import find_place

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


class ItineraryForm(BaseModel):
    itinerary_id: int
    start_time: str = Field(min_length=1, description="in ISO 8601 format", examples=["2026-11-14T09:00:00"])
    end_time: str = Field(min_length=1, description="in ISO 8601 format", examples=["2026-11-16T18:00:00"])

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be less than end_time")
        return self


@router.post("/init", response_model=ItineraryForm, status_code=201)
def init_itinerary(
    itinerary: ItineraryForm,
    database: Annotated[sqlite3.Connection, Depends(get_database)],
) -> ItineraryForm:
    """Initialize an itinerary, deleting and recreating any existing itinerary with the same ID."""
    with database:
        database.execute(
            "DELETE FROM itineraries WHERE itinerary_id = ?", (itinerary.itinerary_id,)
        )
        database.execute(
            "INSERT INTO itineraries (itinerary_id, start_time, end_time) VALUES (?, ?, ?)",
            (itinerary.itinerary_id, itinerary.start_time, itinerary.end_time),
        )
    return itinerary


class Segment(BaseModel):
    segment_id: int
    segment_type: Literal["STOP", "LEG"]
    start_time: str = Field(description="in ISO 8601 format", examples=["2026-11-14T09:00:00"])
    end_time: str = Field(description="in ISO 8601 format", examples=["2026-11-16T18:00:00"])
    place_id: int | None
    place_name: str | None
    place_category: Literal["transport", "accommodation", "attraction", "restaurant", "cafe"] | None
    transport_mode: Literal["WALK", "TRANSIT"] | None


class SegmentForm(BaseModel):
    itinerary_id: int
    segment_type: Literal["STOP", "LEG"]
    start_time: str = Field(description="in ISO 8601 format", examples=["2026-11-14T09:00:00"])
    end_time: str = Field(description="in ISO 8601 format", examples=["2026-11-16T18:00:00"])
    place_id: int | None
    transport_mode: Literal["WALK", "TRANSIT"] | None

    @model_validator(mode="after")
    def validate_segment(self) -> Self:
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be less than end_time")

        if self.segment_type == "STOP":
            valid = self.place_id is not None and self.transport_mode is None
        else:
            valid = self.place_id is None and self.transport_mode is not None

        if not valid:
            raise ValueError("STOP requires only place_id; LEG requires only transport_mode")
        return self


@router.post("/segment", response_model=Segment, status_code=201)
def create_segment(
    segment: SegmentForm,
    database: Annotated[sqlite3.Connection, Depends(get_database)],
) -> Segment:
    """Create a segment within the itinerary's time range without overlapping existing segments."""
    with database:
        database.execute("BEGIN IMMEDIATE")

        itinerary = database.execute(
            "SELECT start_time, end_time FROM itineraries WHERE itinerary_id = ?",
            (segment.itinerary_id,),
        ).fetchone()
        if itinerary is None:
            raise HTTPException(status_code=404, detail="Itinerary not found")
        if segment.start_time < itinerary["start_time"] or segment.end_time > itinerary["end_time"]:
            raise HTTPException(status_code=422, detail="Segment must be within the itinerary's time range")
        
        overlap = database.execute(
            """SELECT 1 FROM segments WHERE itinerary_id = ?
               AND start_time < ? AND end_time > ? LIMIT 1""",
            (segment.itinerary_id, segment.end_time, segment.start_time),
        ).fetchone()
        if overlap is not None:
            raise HTTPException(status_code=409, detail="Segment overlaps an existing segment")

        place = find_place(segment.place_id) if segment.place_id is not None else None
        place_name = place.name if place is not None else None
        place_category = place.category if place is not None else None

        cursor = database.execute(
            """INSERT INTO segments
               (itinerary_id, segment_type, start_time, end_time,
                place_id, place_name, place_category, transport_mode)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (segment.itinerary_id, segment.segment_type, segment.start_time, segment.end_time,
             segment.place_id, place_name, place_category, segment.transport_mode),
        )
        result = Segment(
            **segment.model_dump(exclude={"itinerary_id"}),
            segment_id=cursor.lastrowid,
            place_name=place_name,
            place_category=place_category,
        )
    return result


@router.get("/{itinerary_id}", response_model=list[Segment])
def get_itinerary(
    itinerary_id: int,
    database: Annotated[sqlite3.Connection, Depends(get_database)],
) -> list[Segment]:
    """Retrieve itinerary segments sorted by start time in ascending order."""
    rows = database.execute(
        """SELECT segment_id, segment_type, start_time, end_time,
                  place_id, place_name, place_category, transport_mode
           FROM segments
           WHERE itinerary_id = ?
           ORDER BY start_time ASC, segment_id ASC""",
        (itinerary_id,),
    ).fetchall()
    return [Segment(**dict(row)) for row in rows]


class SegmentPatchForm(BaseModel):
    start_time: str = Field(description="in ISO 8601 format", examples=["2026-11-14T09:00:00"])
    end_time: str = Field(description="in ISO 8601 format", examples=["2026-11-16T18:00:00"])

    model_config = ConfigDict(extra="forbid")


@router.patch("/{itinerary_id}/segment/{segment_id}", response_model=Segment)
def update_segment(
    itinerary_id: int,
    segment_id: int,
    segment: SegmentPatchForm,
    database: Annotated[sqlite3.Connection, Depends(get_database)],
) -> Segment:
    """Update segment start and end times within the itinerary's time range without overlapping other segments."""
    with database:
        database.execute("BEGIN IMMEDIATE")

        row = database.execute(
            "SELECT * FROM segments WHERE itinerary_id = ? AND segment_id = ?",
            (itinerary_id, segment_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Segment not found")

        start_time, end_time = segment.start_time, segment.end_time   
        if start_time >= end_time:
            raise HTTPException(status_code=422, detail="start_time must be less than end_time")

        itinerary = database.execute(
            "SELECT start_time, end_time FROM itineraries WHERE itinerary_id = ?",
            (itinerary_id,),
        ).fetchone()
        if start_time < itinerary["start_time"] or end_time > itinerary["end_time"]:
            raise HTTPException(status_code=422, detail="Segment must be within the itinerary's time range")

        overlap = database.execute(
            """SELECT 1 FROM segments WHERE itinerary_id = ? AND segment_id != ?
               AND start_time < ? AND end_time > ? LIMIT 1""",
            (itinerary_id, segment_id, end_time, start_time),
        ).fetchone()
        if overlap is not None:
            raise HTTPException(status_code=409, detail="Segment overlaps an existing segment")

        database.execute(
            """UPDATE segments SET start_time = ?, end_time = ?
               WHERE itinerary_id = ? AND segment_id = ?""",
            (start_time, end_time, itinerary_id, segment_id),
        )
        result = Segment(**(dict(row) | {"start_time": start_time, "end_time": end_time}))
    return result


@router.delete("/{itinerary_id}/segment/{segment_id}", status_code=204)
def delete_segment(
    itinerary_id: int,
    segment_id: int,
    database: Annotated[sqlite3.Connection, Depends(get_database)],
) -> Response:
    """Delete a segment belonging to the specified itinerary."""
    with database:
        cursor = database.execute(
            "DELETE FROM segments WHERE itinerary_id = ? AND segment_id = ?",
            (itinerary_id, segment_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Segment not found")
    return Response(status_code=204)
