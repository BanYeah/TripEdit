"""TripEdit schedule constraint validation and local persistence.

The travel-time callback uses the SAME GraphHopper adapter/cache as /travel-time.
No made-up durations are ever used: an unavailable route is a validation error.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from app.hours import is_open_for
from app.models import Issue, Mode, Place, PlanInput, PlanReport, Visit, TravelTimeOut
from app.places import normalize_place_id

SEOUL = ZoneInfo('Asia/Seoul')
TravelTimeFn = Callable[[Place, Place, Mode, datetime], Awaitable[TravelTimeOut]]


class ItineraryStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS itineraries (id TEXT PRIMARY KEY, data_json TEXT NOT NULL, updated_at TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def load(self, itinerary_id: str) -> PlanInput | None:
        with self.connect() as db:
            found = db.execute('SELECT data_json FROM itineraries WHERE id=?', (itinerary_id,)).fetchone()
        return PlanInput.model_validate_json(found[0]) if found else None

    def save(self, itinerary_id: str, plan: PlanInput):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO itineraries(id,data_json,updated_at) VALUES(?,?,?)',
                       (itinerary_id, plan.model_dump_json(), datetime.now(SEOUL).isoformat()))


async def validate_plan(plan: PlanInput, places: dict[str, Place], get_travel_time: TravelTimeFn,
                        previous: PlanInput | None = None) -> PlanReport:
    errors: list[Issue] = []
    legs: list[dict] = []
    original_visits = {v.visit_id: v for v in previous.visits} if previous else {}
    current_visits = {v.visit_id: v for v in plan.visits}

    if len(current_visits) < len(plan.visits):
        errors.append(Issue(code='duplicate_visit_id', message='visit_id must be unique'))
    if plan.preserve_existing:
        allowed = set(plan.allowed_change_visit_ids)
        for visit_id, original in original_visits.items():
            if visit_id not in allowed and current_visits.get(visit_id) != original:
                errors.append(Issue(code='preserve_existing', message='Existing visit cannot be silently changed or removed', visit_ids=[visit_id]))

    # Sort even malformed inputs safely; missing timezones become validation errors.
    def sort_instant(visit: Visit):
        dt = visit.start_at
        return dt.replace(tzinfo=SEOUL).timestamp() if dt.tzinfo is None else dt.timestamp()
    visits = sorted(plan.visits, key=sort_instant)
    enriched: list[tuple[Visit, Place, int, datetime, datetime]] = []
    per_meal: dict[tuple[str, str], str] = {}
    for visit in visits:
        place_id = normalize_place_id(visit.place_id)
        place = places.get(place_id)
        if place is None:
            errors.append(Issue(code='unknown_place', message=f'Unknown place: {place_id}', visit_ids=[visit.visit_id]))
            continue
        if visit.start_at.utcoffset() is None:
            errors.append(Issue(code='timezone_required', message='start_at needs a timezone such as +09:00', visit_ids=[visit.visit_id]))
            continue
        duration = visit.duration_minutes if visit.duration_minutes is not None else place.min_duration
        if not duration:
            errors.append(Issue(code='duration_required', message='No explicit duration and no default min_duration', visit_ids=[visit.visit_id]))
            continue
        start = visit.start_at.astimezone(SEOUL)
        end = start + timedelta(minutes=duration)
        if not is_open_for(place.opening_hours, start, duration):
            errors.append(Issue(code='outside_opening_hours', message=f'{place.name} is not open for entire visit', visit_ids=[visit.visit_id], details={'start_at': start.isoformat(), 'duration_minutes': duration}))
        if place.category == 'restaurant' and not visit.explicit_time_override:
            minute = start.hour * 60 + start.minute
            end_minute = minute + duration
            lunch = 11 * 60 <= minute and end_minute <= 15 * 60
            dinner = 17 * 60 <= minute and end_minute <= 20 * 60
            if not (lunch or dinner):
                errors.append(Issue(code='restaurant_meal_window', message='Restaurant must fit entirely within lunch 11:00-15:00 or dinner 17:00-20:00; explicit_time_override can relax this default', visit_ids=[visit.visit_id]))
            else:
                key = (start.date().isoformat(), 'lunch' if lunch else 'dinner')
                earlier = per_meal.get(key)
                if earlier:
                    errors.append(Issue(code='duplicate_meal', message='At most one restaurant per meal window', visit_ids=[earlier, visit.visit_id]))
                else:
                    per_meal[key] = visit.visit_id
        enriched.append((visit, place, duration, start, end))

    for (old, old_place, _, old_start, old_end), (new, new_place, _, new_start, _) in zip(enriched, enriched[1:]):
        if new_start < old_end:
            errors.append(Issue(code='overlap', message='Visits overlap', visit_ids=[old.visit_id, new.visit_id]))
            continue
        if old_start.date() != new_start.date():
            legs.append({'from_visit_id': old.visit_id, 'to_visit_id': new.visit_id, 'checked': False, 'reason': 'different_calendar_day'})
            continue
        try:
            route = await get_travel_time(old_place, new_place, new.mode_from_previous, old_end)
        except Exception as exc:
            # Caller translates engine errors for endpoint; validation never guesses.
            from fastapi import HTTPException
            if isinstance(exc, HTTPException):
                message = str(exc.detail)
            else:
                message = f'{type(exc).__name__}: {exc}'
            errors.append(Issue(code='route_unavailable', message=message, visit_ids=[old.visit_id, new.visit_id]))
            continue
        available_minutes = int((new_start - old_end).total_seconds() // 60)
        leg = {
            'from_visit_id': old.visit_id,
            'to_visit_id': new.visit_id,
            'mode': new.mode_from_previous.value,
            'departure_at': old_end.isoformat(),
            'required_minutes': route.duration_minutes,
            'available_minutes': available_minutes,
            'cached': route.cached,
            'checked': True,
        }
        legs.append(leg)
        if available_minutes < route.duration_minutes:
            errors.append(Issue(code='insufficient_travel_time', message='Not enough travel time between visits', visit_ids=[old.visit_id, new.visit_id], details=leg))
    return PlanReport(valid=not errors, errors=errors, travel_legs=legs)
