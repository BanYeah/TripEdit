from __future__ import annotations

import asyncio

import httpx
import pytest

from app.graphhopper import GraphHopperClient
from app.models import EngineError, Mode, Place, RouteNotFound


A = Place("1", "A", 35.15, 129.12)
B = Place("2", "B", 35.11, 129.04)


def test_route_request_parameters():
    seen = []

    def respond(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={"paths": [{"time": 2100000, "distance": 5000, "num_changes": 2}, {"time": 1500000, "distance": 6000, "num_changes": 1}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            gh = GraphHopperClient("http://gh.local:8989", client=client)
            from datetime import datetime, timezone, timedelta
            depart = datetime(2026, 11, 9, 13, 0, tzinfo=timezone(timedelta(hours=9)))
            route = await gh.route(A, B, Mode.TRANSIT, depart)
            assert route.duration_ms == 1500000
            assert route.transfer_count == 1
            p = seen[0].url.params
            assert p.get_list("point") == ["35.1500000,129.1200000", "35.1100000,129.0400000"]
            assert p["profile"] == "pt"
            assert p["pt.earliest_departure_time"] == "2026-11-09T04:00:00Z"
            assert p["pt.arrive_by"] == "false"
            walked = await gh.route(A, B, Mode.WALK, None)
            assert walked.transfer_count is None
            assert seen[1].url.params["profile"] == "foot"
            assert "pt.earliest_departure_time" not in seen[1].url.params
    asyncio.run(run())


def test_no_route_and_upstream_failure():
    async def run(payload, status=200):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=payload))) as c:
            gh = GraphHopperClient("http://gh.local", client=c)
            return await gh.route(A, B, Mode.WALK, None)
    with pytest.raises(RouteNotFound):
        asyncio.run(run({"paths": []}))
    with pytest.raises(EngineError):
        asyncio.run(run({"message": "bad profile"}, 400))
