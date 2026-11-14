import os
import asyncio
from contextlib import asynccontextmanager

from enum import Enum
from typing import Annotated
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(
        base_url=os.getenv("GRAPHHOPPER_URL", "http://127.0.0.1:8989"),
        timeout=httpx.Timeout(120, connect=5),
        trust_env=False,
    ) as client:
        app.state.client = client
        yield


app = FastAPI(
    title="TripEdit Route API",
    version="1.0.0",
    lifespan=lifespan,
    description="OSM 도보 및 GTFS 시간표 기반 대중교통 이동 시간.",
)

SEOUL = ZoneInfo("Asia/Seoul")
WALK_SPEED_KMH = 4.0
MAX_WALK_DURATION_SECONDS = 90 * 60
WALK_CUSTOM_MODEL = {"speed": [{"if": "road_environment != FERRY", "multiply_by": str(WALK_SPEED_KMH / 5.0)}]}


class Mode(str, Enum):
    walk = "walk"
    transit = "transit"


class Point(BaseModel):
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]

    def query(self):
        return f"{self.lat},{self.lon}"


class RouteForm(BaseModel):
    origin: Point
    destination: Point
    departure_time: str = Field(description="in ISO 8601 format", examples=["2026-11-14T09:00:00"])
    max_solutions: Annotated[int, Field(ge=1, le=5)] = 3
    include_geometry: bool = False

    @field_validator("departure_time")
    @classmethod
    def validate_departure_time(cls, value):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("departure_time은 ISO 8601 형식이어야 합니다.") from None
        
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=SEOUL)
        return parsed.isoformat()

    @property
    def departure_datetime(self):
        return datetime.fromisoformat(self.departure_time)


async def backend(client, endpoint, params, timeout=None, *, json_body=None):
    try:
        options = {} if timeout is None else {"timeout": timeout}
        if json_body is None:
            response = await client.get(endpoint, params=params, **options)
        else:
            response = await client.post(endpoint, json=json_body, **options)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "GraphHopper 경로 탐색 시간이 초과되었습니다.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, "GraphHopper에 연결할 수 없습니다. 엔진 실행 또는 초기 그래프 생성 상태를 확인하세요.") from exc
    
    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(502, "GraphHopper가 JSON이 아닌 응답을 반환했습니다.") from exc
    
    if not response.is_success:
        detail = payload.get("message", "경로를 찾을 수 없습니다.")
        raise HTTPException(422 if response.status_code == 400 else 502, detail)
    return payload


def timestamp(value):
    if isinstance(value, (float, int)):
        return datetime.fromtimestamp(value / 1000, timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize(path, query, transit):
    legs = path.get("legs", [])  # 이동 구간
    boardings = sum(leg.get("type") == "pt" for leg in legs) # 승차 구간
    distance_complete = all(leg.get("distance", 0) > 0 for leg in legs if leg.get("type") == "pt")

    duration = path["time"] / 1000
    walk_seconds = sum((timestamp(leg["arrival_time"]) - timestamp(leg["departure_time"])).total_seconds()
                       for leg in legs if leg.get("type") == "walk")
    
    result = {
        "kind": "transit" if boardings else "walk",
        "duration_seconds": duration,
        "duration_minutes": round(duration / 60, 2),
        "distance_meters": path["distance"] if distance_complete else None,
        "distance_is_complete": distance_complete,
        "walking_distance_meters": round(sum(leg.get("distance", 0) for leg in legs
                                              if leg.get("type") == "walk"), 3) if transit else path["distance"],
        "transfers": max(0, path.get("transfers", boardings - 1)) if boardings else 0,
        "walking_seconds": round(walk_seconds if transit else duration, 3),
        "legs": legs,
    }

    if transit and legs:
        departure = timestamp(legs[0]["departure_time"])
        arrival = timestamp(legs[-1]["arrival_time"])
        result.update({
            "departure_time": departure.astimezone(SEOUL).isoformat(),
            "arrival_time": arrival.astimezone(SEOUL).isoformat(),
            "elapsed_seconds_from_request": round((arrival - query.departure_datetime).total_seconds(), 3),
        })
    
    if query.include_geometry:
        result["geometry"] = path.get("points")
        result["geometry_encoded"] = path.get("points_encoded", False)
    else:
        result["legs"] = [{k: v for k, v in leg.items() if k not in ("geometry", "instructions")} for leg in legs]
    
    return result


async def calculate(client, query, mode):
    json_body = None
    params = [("point", query.origin.query()), ("point", query.destination.query())]

    if mode == Mode.walk:
        endpoint = "/route"
        json_body = {
            "profile": "foot",
            "points": [[query.origin.lon, query.origin.lat], [query.destination.lon, query.destination.lat]],
            "custom_model": WALK_CUSTOM_MODEL,
            "points_encoded": False,
            "instructions": False,
            "calc_points": query.include_geometry,
        }
    else: # transit
        endpoint = "/route-pt"
        params += [
            ("pt.earliest_departure_time", query.departure_time),
            ("pt.profile", "false"),
            ("pt.limit_solutions", str(query.max_solutions)),
            ("pt.access_profile", "foot"),
            ("pt.egress_profile", "foot"),
        ]
    
    try:
        payload = await backend(client, endpoint, params, json_body=json_body)
        routes = [normalize(path, query, mode == Mode.transit) for path in payload.get("paths", [])]
        retained = [route for route in routes if route["kind"] != "walk" or route["duration_seconds"] <= MAX_WALK_DURATION_SECONDS]
        if routes and not retained:
            return {"status": "duration_limit_exceeded", "max_duration_minutes": 90, "routes": []}
        routes = retained
        return {"status": "ok" if routes else "no_route", "routes": routes}
    except HTTPException as exc:
        return {"status": "error", "status_code": exc.status_code, "message": exc.detail, "routes": []}
    except (KeyError, ValueError, TypeError) as exc:
        return {"status": "error", "status_code": 502, "message": f"GraphHopper 응답 형식 오류: {type(exc).__name__}", "routes": []}


@app.get("/health")
async def health(request: Request):
    await backend(request.app.state.client, "/info", [], timeout=3)
    return {"status": "ok", "graphhopper": "ready"}


@app.post("/routes")
async def routes(route: RouteForm, request: Request, response: Response):
    modes = [Mode.walk, Mode.transit]
    results = await asyncio.gather(*(calculate(request.app.state.client, route, mode) for mode in modes))
    if all(result["status"] == "error" for result in results):
        response.status_code = results[0]["status_code"]
    return {
        "departure_time": route.departure_datetime.astimezone(SEOUL).isoformat(),
        "results": {mode.value: result for mode, result in zip(modes, results)},
        "attribution": ["© OpenStreetMap contributors", "GTFS: KTDB"],
    }
