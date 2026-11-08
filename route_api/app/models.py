"""Typed contracts for routes, places and schedule validation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Mode(str, Enum):
    WALK = 'WALK'
    TRANSIT = 'TRANSIT'


@dataclass(frozen=True)
class Place:
    place_id: str
    name: str
    latitude: float | None
    longitude: float | None
    category: str = 'restaurant'
    opening_hours: dict[str, list[list[str]]] | None = None
    min_duration: int | None = None
    place_url: str = ''

    @property
    def routable(self) -> bool:
        return self.latitude is not None and self.longitude is not None


@dataclass(frozen=True)
class Route:
    duration_ms: int
    distance_meters: float | None
    transfer_count: int | None


class RouteNotFound(Exception):
    pass


class EngineError(Exception):
    pass


class EngineTimeout(EngineError):
    pass


class PlaceOut(BaseModel):
    place_id: str
    name: str
    latitude: float | None = None
    longitude: float | None = None
    routable: bool
    category: str = 'restaurant'
    opening_hours: dict[str, list[list[str]]] | None = None
    min_duration: int | None = None
    place_url: str = ''


class TravelTimeOut(BaseModel):
    from_id: str
    to_id: str
    mode: Mode
    duration_minutes: int = Field(ge=0)
    duration_seconds: int = Field(ge=0)
    distance_meters: float | None
    transfer_count: int | None
    departure_requested: datetime | None
    departure_calculated: datetime | None
    approximate_departure: bool
    source: str
    cached: bool
    data_version: str


class Visit(BaseModel):
    visit_id: str = Field(min_length=1, max_length=128)
    place_id: str = Field(min_length=1)
    start_at: datetime
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    # Mode used from the preceding visit TO this visit.
    mode_from_previous: Mode = Mode.TRANSIT
    # Explicit user preference to ignore restaurant lunch/dinner default rule.
    explicit_time_override: bool = False


class PlanInput(BaseModel):
    visits: list[Visit] = Field(default_factory=list, max_length=100)
    # If set, checks that an existing itinerary is preserved except specific IDs.
    preserve_existing: bool = True
    allowed_change_visit_ids: list[str] = Field(default_factory=list)


class PlanSave(PlanInput):
    itinerary_id: str = Field(min_length=1, max_length=128)


class Issue(BaseModel):
    code: str
    message: str
    visit_ids: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class PlanReport(BaseModel):
    valid: bool
    errors: list[Issue]
    travel_legs: list[dict[str, Any]]
    saved: bool = False
    itinerary_id: str | None = None


class EditRequest(BaseModel):
    """One explicit multi-turn modification. No natural-language guessing."""
    action: Literal['add', 'replace', 'move', 'delete']
    visit_id: str = Field(min_length=1)
    place_id: str | None = None
    start_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    mode_from_previous: Mode | None = None
    explicit_time_override: bool | None = None
