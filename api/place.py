import csv
import json
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path as PathParam, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/place", tags=["place"])

DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"
PLACE_FILES = (
    "transport.csv",
    "accommodation.csv",
    "attraction.csv",
    "restaurant.csv",
    "cafe.csv",
)


class PlaceLocation(BaseModel):
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False, examples=[131.869556])
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False, examples=[37.240778])


class Place(BaseModel):
    place_id: int
    name: str
    category: Literal["transport", "accommodation", "attraction", "restaurant", "cafe"]


class TransportInfo(BaseModel):
    category: Literal["transport"]
    arrival_after: int = Field(description="Required extra time after arrival in minutes")
    departure_before: int = Field(description="Required extra time before departure in minutes")


class AccommodationInfo(BaseModel):
    category: Literal["accommodation"]
    check_in: str = Field(examples=["15:00-24:00"])
    check_out: str = Field(examples=["11:00"])


class VisitPlaceInfo(BaseModel):
    category: Literal["attraction", "restaurant", "cafe"]
    opening_hours: dict[str, list[list[str]]] = Field(
        description="Opening time intervals by weekday; an empty list indicates a closed day",
        examples=[{
            "mon": [["10:00", "13:00"], ["14:00", "21:00"]],
            "tue": [["10:00", "13:00"], ["14:00", "21:00"]],
            "wed": [["10:00", "21:00"]],
            "thu": [["10:00", "21:00"]],
            "fri": [["10:00", "21:00"]],
            "sat": [],
            "sun": [],
        }],
    )
    min_duration: int = Field(description="Minimum visit duration in minutes")


PlaceInfo = Annotated[
    TransportInfo | AccommodationInfo | VisitPlaceInfo,
    Field(discriminator="category"),
]


@router.get("/search", response_model=list[Place])
def search_places(
    name: Annotated[str, Query(min_length=1, pattern=r"\S", description="Place name")],
) -> list[Place]:
    """Find places whose names contain the given text."""
    results = []
    keyword = name.strip().casefold()
    for filename in PLACE_FILES:
        with (DATASET_DIR / filename).open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                if keyword in row["name"].casefold():
                    results.append(Place(
                        place_id=int(row["place_id"]),
                        name=row["name"],
                        category=row["category"],
                    ))
    return results


@router.get("/{place_id}/information", response_model=PlaceInfo, summary="Get Place Information")
def get_place_info(
    place_id: Annotated[int, PathParam(description="Place ID")],
) -> PlaceInfo:
    """Retrieve category-specific information for a place by its ID."""
    for filename in PLACE_FILES:
        with (DATASET_DIR / filename).open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                if int(row["place_id"]) != place_id:
                    continue

                category = row["category"]
                if category == "transport":
                    return TransportInfo(
                        category=category,
                        arrival_after=int(row["arrival_after"]),
                        departure_before=int(row["departure_before"]),
                    )
                if category == "accommodation":
                    return AccommodationInfo(
                        category=category, 
                        check_in=row["check-in"], 
                        check_out=row["check-out"],
                    )
                return VisitPlaceInfo(
                    category=category,
                    opening_hours=json.loads(row["opening_hours"]),
                    min_duration=int(row["min_duration"]),
                )

    raise HTTPException(status_code=404, detail="Place not found for the provided ID.")


@router.get("/{place_id}/location", response_model=PlaceLocation)
def get_place_location(
    place_id: Annotated[int, PathParam(description="Place ID")],
) -> PlaceLocation:
    """Retrieve the longitude and latitude of a place by its ID."""
    for filename in PLACE_FILES:
        with (DATASET_DIR / filename).open(encoding="utf-8-sig", newline="") as file:
            for row in csv.DictReader(file):
                if int(row["place_id"]) != place_id:
                    continue

                return PlaceLocation(
                    longitude=float(row["longitude"]),
                    latitude=float(row["latitude"]),
                )

    raise HTTPException(status_code=404, detail="Place not found for the provided ID.")
