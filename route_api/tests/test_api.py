from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_and_readiness(test_context):
    app, _ = test_context
    with TestClient(app) as client:
        h = client.get("/health")
        assert h.status_code == 200
        assert h.json()["routable_places"] == 2
        assert client.get("/ready").status_code == 200
        places = client.get("/places").json()
        assert len(places) == 3
        assert next(p for p in places if p["place_id"] == "103")["routable"] is False


def test_walk_route_cache_and_identity(test_context):
    app, engine = test_context
    with TestClient(app) as client:
        params = {"from_id": "101", "to_id": "102", "mode": "WALK"}
        first = client.get("/travel-time", params=params)
        assert first.status_code == 200, first.text
        a = first.json()
        assert a["duration_minutes"] == 9  # always round up for scheduling safety
        assert a["cached"] is False
        assert a["source"] == "graphhopper"
        assert len(engine.calls) == 1
        second = client.get("/travel-time", params=params)
        assert second.status_code == 200
        assert second.json()["cached"] is True
        assert len(engine.calls) == 1
        same = client.get("/travel-time", params={"from_id": "103", "to_id": "103"})
        assert same.status_code == 200
        assert same.json()["duration_minutes"] == 0
        assert len(engine.calls) == 1
        refreshed = client.get("/travel-time", params={**params, "refresh": True})
        assert refreshed.status_code == 200
        assert len(engine.calls) == 2


def test_transit_timezone_validation_and_cache(test_context):
    app, engine = test_context
    with TestClient(app) as client:
        params = {"from_id": "101", "to_id": "102", "mode": "TRANSIT"}
        assert client.get("/travel-time", params=params).status_code == 422
        assert client.get("/travel-time", params={**params, "departure": "2026-11-09T13:00:00"}).status_code == 422
        valid = client.get("/travel-time", params={**params, "departure": "2026-11-09T13:07:34+09:00"})
        assert valid.status_code == 200, valid.text
        result = valid.json()
        assert result["approximate_departure"] is True
        assert result["departure_calculated"].startswith("2026-11-09T13:08:00")
        assert result["duration_minutes"] == 37
        assert result["transfer_count"] == 1
        assert engine.calls[-1][3].second == 0
        assert client.get("/travel-time", params={"from_id": "102", "to_id": "101"}).json()["cached"] is False


def test_missing_locations_error_and_bad_mode(test_context):
    app, engine = test_context
    with TestClient(app) as client:
        assert client.get("/travel-time", params={"from_id": "UNKNOWN", "to_id": "102"}).status_code == 404
        fail = client.get("/travel-time", params={"from_id": "103", "to_id": "102"})
        assert fail.status_code == 409
        assert fail.json()["detail"]["error"] == "missing_coordinates"
        assert client.get("/travel-time", params={"from_id": "101", "to_id": "102", "mode": "DRIVE"}).status_code == 422
        assert engine.calls == []
