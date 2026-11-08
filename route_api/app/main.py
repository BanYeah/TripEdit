"""TripEdit local API: restaurant registry, OSM/GTFS routes, and schedule checks."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from app.cache import SqliteRouteCache
from app.config import Settings
from app.graphhopper import GraphHopperClient
from app.itineraries import ItineraryStore, validate_plan
from app.models import EngineError, EngineTimeout, Mode, Place, PlaceOut, PlanInput, PlanReport, Route, RouteNotFound, TravelTimeOut, EditRequest, Visit
from app.places import load_places, normalize_place_id


def departure_for_bucket(dt: datetime, bucket_minutes: int) -> datetime:
    """Round UP: never include a train departing before the requested time.

    The response adds the small waiting gap to the calculated journey duration.
    """
    minute = dt.minute - dt.minute % bucket_minutes
    bucket_start = dt.replace(minute=minute, second=0, microsecond=0)
    return bucket_start if bucket_start == dt else bucket_start + timedelta(minutes=bucket_minutes)


def create_app(settings: Settings | None = None, engine: Any | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    places = load_places(cfg.places_csv)
    cache = SqliteRouteCache(cfg.cache_db)
    store = ItineraryStore(cfg.cache_db.with_name('itineraries.sqlite3'))
    engine = engine or GraphHopperClient(cfg.graph_hopper_url, cfg.http_timeout_seconds)
    app = FastAPI(title='TripEdit Busan Route & Itinerary API', version='0.2.0',
                  description='Self-hosted OSM/GTFS routing; source restaurant workbook; deterministic schedule validation')

    async def travel(origin: Place, dest: Place, mode: Mode, departure: datetime | None,
                     refresh: bool = False) -> TravelTimeOut:
        if mode == Mode.TRANSIT and departure is None:
            raise HTTPException(422, 'TRANSIT requires departure with a timezone (e.g. +09:00)')
        if departure is not None and (departure.tzinfo is None or departure.utcoffset() is None):
            raise HTTPException(422, 'Departure must include timezone, e.g. +09:00')
        calculated = departure_for_bucket(departure, cfg.transit_bucket_minutes) if mode is Mode.TRANSIT else None
        approx = bool(mode is Mode.TRANSIT and calculated != departure)

        def response(route: Route, cached: bool, source: str) -> TravelTimeOut:
            # GraphHopper PT duration starts at the rounded-up query departure.
            # Include waiting from the actual requested departure to that bucket.
            rounding_wait_ms = 0
            if mode is Mode.TRANSIT and calculated is not None and departure is not None and origin.place_id != dest.place_id:
                rounding_wait_ms = max(0, math.ceil((calculated - departure).total_seconds() * 1000))
            effective_duration_ms = route.duration_ms + rounding_wait_ms
            return TravelTimeOut(
                from_id=origin.place_id, to_id=dest.place_id, mode=mode,
                duration_minutes=math.ceil(effective_duration_ms / 60000),
                duration_seconds=math.ceil(effective_duration_ms / 1000),
                distance_meters=route.distance_meters, transfer_count=route.transfer_count,
                departure_requested=departure, departure_calculated=calculated,
                approximate_departure=approx, source=source, cached=cached,
                data_version=cfg.data_version,
            )

        if origin.place_id == dest.place_id:
            return response(Route(0, 0.0, 0 if mode is Mode.TRANSIT else None), False, 'same-place')
        if not origin.routable or not dest.routable:
            missing = [p.place_id for p in (origin, dest) if not p.routable]
            raise HTTPException(409, detail={'error': 'missing_coordinates', 'place_ids': missing})

        key_payload = [cfg.data_version, origin.place_id, origin.latitude, origin.longitude,
                       dest.place_id, dest.latitude, dest.longitude, mode.value,
                       calculated.isoformat() if calculated else None]
        key = hashlib.sha256(json.dumps(key_payload, ensure_ascii=False).encode()).hexdigest()
        ttl = cfg.transit_cache_ttl_seconds if mode is Mode.TRANSIT else cfg.walk_cache_ttl_seconds
        if not refresh:
            hit = cache.get(key, ttl)
            if hit is not None:
                return response(hit, True, 'graphhopper-cache')
        try:
            route = await engine.route(origin, dest, mode, calculated)
        except RouteNotFound as exc:
            raise HTTPException(404, str(exc)) from exc
        except EngineTimeout as exc:
            raise HTTPException(504, str(exc)) from exc
        except EngineError as exc:
            raise HTTPException(502, str(exc)) from exc
        cache.put(key, route)
        return response(route, False, 'graphhopper')

    @app.get('/health')
    def health():
        return {
            'service': 'ok', 'total_places': len(places),
            'routable_places': sum(p.routable for p in places.values()),
            'data_version': cfg.data_version, 'engine_checked': False,
        }

    @app.get('/ready')
    async def ready():
        if sum(p.routable for p in places.values()) < 2:
            raise HTTPException(503, 'At least two places need latitude/longitude in PLACES_CSV. Run Kakao coordinate enrichment.')
        if not await engine.available():
            raise HTTPException(503, 'GraphHopper not reachable; verify GET /info at GRAPH_HOPPER_URL')
        return {'ready': True, 'note': 'WALK/PT profiles and GTFS coverage must be verified with real route smoke tests.'}

    @app.get('/places', response_model=list[PlaceOut])
    def get_places():
        return [PlaceOut(**p.__dict__, routable=p.routable) for p in places.values()]

    @app.get('/places/{place_id}', response_model=PlaceOut)
    def get_place(place_id: str):
        place = places.get(normalize_place_id(place_id))
        if not place:
            raise HTTPException(404, 'Unknown place')
        return PlaceOut(**place.__dict__, routable=place.routable)

    @app.get('/travel-time', response_model=TravelTimeOut)
    async def travel_time(
        from_id: str = Query(..., min_length=1),
        to_id: str = Query(..., min_length=1),
        mode: Mode = Query(Mode.WALK),
        departure: datetime | None = Query(None, description='ISO-8601; timezone required for TRANSIT'),
        refresh: bool = Query(False),
    ):
        orig = places.get(normalize_place_id(from_id))
        dest = places.get(normalize_place_id(to_id))
        if not orig:
            raise HTTPException(404, f'Unknown from_id: {from_id}')
        if not dest:
            raise HTTPException(404, f'Unknown to_id: {to_id}')
        return await travel(orig, dest, mode, departure, refresh)

    @app.post('/itineraries/validate', response_model=PlanReport,
              summary='Dry-run itinerary validation (does not save)')
    async def validate(plan: PlanInput):
        return await validate_plan(plan, places, travel)

    @app.get('/itineraries/{itinerary_id}', response_model=PlanInput)
    def get_itinerary(itinerary_id: str):
        plan = store.load(itinerary_id)
        if plan is None:
            raise HTTPException(404, 'Itinerary not found')
        return plan

    @app.put('/itineraries/{itinerary_id}', response_model=PlanReport,
             summary='Save only if schedule, opening hours and travel constraints pass')
    async def save_itinerary(itinerary_id: str, plan: PlanInput):
        old = store.load(itinerary_id)
        report = await validate_plan(plan, places, travel, old)
        report.itinerary_id = itinerary_id
        if not report.valid:
            raise HTTPException(409, detail=report.model_dump(mode='json'))
        store.save(itinerary_id, plan)
        report.saved = True
        return report

    @app.post('/itineraries/{itinerary_id}/edit', response_model=PlanReport,
              summary='Apply exactly one explicit add/replace/move/delete turn')
    async def edit_itinerary(itinerary_id: str, change: EditRequest):
        old = store.load(itinerary_id)
        if old is None:
            raise HTTPException(404, 'Itinerary not found; create it with PUT first')
        current = {v.visit_id: v for v in old.visits}
        if change.action == 'add':
            if change.visit_id in current:
                raise HTTPException(409, 'visit_id already exists')
            if not change.place_id or not change.start_at:
                raise HTTPException(422, 'add requires place_id and start_at')
            current[change.visit_id] = Visit(
                visit_id=change.visit_id, place_id=change.place_id, start_at=change.start_at,
                duration_minutes=change.duration_minutes,
                mode_from_previous=change.mode_from_previous or Mode.TRANSIT,
                explicit_time_override=bool(change.explicit_time_override),
            )
        else:
            if change.visit_id not in current:
                raise HTTPException(404, f'Visit not found: {change.visit_id}')
            if change.action == 'delete':
                del current[change.visit_id]
            else:
                updates = {}
                if change.action == 'replace':
                    if not change.place_id:
                        raise HTTPException(422, 'replace requires place_id')
                    updates['place_id'] = change.place_id
                elif change.action == 'move':
                    if change.start_at is None:
                        raise HTTPException(422, 'move requires start_at')
                    updates['start_at'] = change.start_at
                    # Explicitly changed time is a user choice; relax meal defaults only.
                    updates['explicit_time_override'] = True
                if change.duration_minutes is not None:
                    updates['duration_minutes'] = change.duration_minutes
                if change.mode_from_previous is not None:
                    updates['mode_from_previous'] = change.mode_from_previous
                if change.explicit_time_override is not None:
                    updates['explicit_time_override'] = change.explicit_time_override
                current[change.visit_id] = current[change.visit_id].model_copy(update=updates)
        proposal = PlanInput(
            visits=list(current.values()), preserve_existing=True,
            allowed_change_visit_ids=[change.visit_id],
        )
        report = await validate_plan(proposal, places, travel, old)
        report.itinerary_id = itinerary_id
        if not report.valid:
            raise HTTPException(409, detail=report.model_dump(mode='json'))
        store.save(itinerary_id, proposal)
        report.saved = True
        return report

    return app


app = create_app()
