"""GraphHopper self-hosted REST client. Walking and GTFS/PT use GET /route."""
from __future__ import annotations

import math
from datetime import datetime, timezone

import httpx

from app.models import EngineError, EngineTimeout, Mode, Place, Route, RouteNotFound


class GraphHopperClient:
    def __init__(self, base_url: str, timeout_seconds: float = 20, client: httpx.AsyncClient | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = client

    async def available(self) -> bool:
        try:
            if self._client is not None:
                response = await self._client.get(f"{self.base_url}/info", timeout=self.timeout_seconds)
            else:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.get(f"{self.base_url}/info")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def route(self, origin: Place, destination: Place, mode: Mode, departure: datetime | None) -> Route:
        if not origin.routable or not destination.routable:
            raise ValueError("Coordinates required")
        params: list[tuple[str, str]] = [
            ("point", f"{origin.latitude:.7f},{origin.longitude:.7f}"),
            ("point", f"{destination.latitude:.7f},{destination.longitude:.7f}"),
            ("profile", "pt" if mode is Mode.TRANSIT else "foot"),
            ("locale", "ko"),
            ("points_encoded", "false"),
        ]
        if mode is Mode.TRANSIT:
            if departure is None or departure.tzinfo is None or departure.utcoffset() is None:
                raise ValueError("Transit requires a timezone-aware departure")
            utc_departure = departure.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            params.extend([
                ("pt.earliest_departure_time", utc_departure),
                ("pt.arrive_by", "false"),
                ("pt.profile", "false"),
                ("pt.limit_street_time", "PT45M"),
            ])
        try:
            if self._client is not None:
                res = await self._client.get(f"{self.base_url}/route", params=params, timeout=self.timeout_seconds)
            else:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    res = await client.get(f"{self.base_url}/route", params=params)
        except httpx.TimeoutException as exc:
            raise EngineTimeout("GraphHopper response timeout") from exc
        except httpx.HTTPError as exc:
            raise EngineError(f"Could not contact GraphHopper: {exc}") from exc

        if res.status_code != 200:
            error_text = res.text[:300]
            if res.status_code in (400, 404) and "cannot find" in error_text.lower():
                raise RouteNotFound("GraphHopper cannot find a route")
            raise EngineError(f"GraphHopper HTTP {res.status_code}: {error_text}")
        try:
            payload = res.json()
            paths = payload.get("paths") or []
            if not paths:
                raise RouteNotFound("No route found for that departure/GTFS calendar")
            # A transit result may list several Pareto alternatives. For the benchmark,
            # choose minimum elapsed duration, not route length in metres.
            candidate = min(paths, key=lambda p: float(p["time"]))
            duration_ms = int(math.ceil(float(candidate["time"])))
            if duration_ms < 0:
                raise ValueError("Negative time")
            distance = candidate.get("distance")
            changes = candidate.get("num_changes")
            return Route(
                duration_ms=duration_ms,
                distance_meters=float(distance) if distance is not None else None,
                transfer_count=int(changes) if changes is not None and mode is Mode.TRANSIT else None,
            )
        except RouteNotFound:
            raise
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise EngineError("Unexpected GraphHopper response format") from exc
