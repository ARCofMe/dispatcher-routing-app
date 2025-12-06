import copy

import pytest

from services.routing_service import RoutingService


@pytest.fixture
def routing():
    r = RoutingService()
    # Avoid network geocoding during tests
    r._geocode = lambda addr: (0.0, 0.0)
    return r


def test_preserves_duplicate_stops_order(routing):
    stops = [
        {"id": "A1", "address": "123 Demo", "lat": 1.0, "lon": 1.0},
        {"id": "A1", "address": "123 Demo", "lat": 2.0, "lon": 2.0},
    ]
    result = routing.preview_route(copy.deepcopy(stops))
    assert len(result["stops"]) == 2
    assert result["stops"][0]["lat"] == 1.0
    assert result["stops"][1]["lat"] == 2.0


def test_metrics_include_origin_destination(routing):
    stops = [
        {"id": "A1", "address": "123 Demo", "lat": 1.0, "lon": 1.0},
        {"id": "A2", "address": "456 Demo", "lat": 2.0, "lon": 2.0},
    ]
    routing._geocode = lambda addr: (3.0, 3.0)  # lon, lat
    result = routing.preview_route(copy.deepcopy(stops), origin="Orig", destination="Dest")
    metrics = result["metrics"]
    assert metrics["includes_origin_destination"] is True
    # Path should include origin and destination points (2 stops + 2 geocoded points)
    assert len(result["path"]) == 4


def test_missing_coordinates_are_geocoded(routing):
    calls = []
    routing._geocode = lambda addr: calls.append(addr) or (5.0, 6.0)
    stops = [
        {"id": "A1", "address": "123 Demo", "lat": None, "lon": None},
        {"id": "A2", "address": "456 Demo", "lat": 2.0, "lon": 2.0},
    ]
    result = routing.preview_route(copy.deepcopy(stops))
    latlons = [(s["lat"], s["lon"]) for s in result["stops"]]
    assert latlons[0] == (5.0, 6.0)
    assert latlons[1] == (2.0, 2.0)
    assert "123 Demo" in calls


def test_simulate_respects_manual_order(routing):
    routing._geocode = lambda addr: (1.0, 1.0)
    stops = [
        {"id": "A", "address": "addrA", "lat": 0.0, "lon": 0.0},
        {"id": "B", "address": "addrB", "lat": 0.0, "lon": 1.0},
        {"id": "C", "address": "addrC", "lat": 0.0, "lon": 2.0},
    ]
    manual_order = ["C", "A", "B"]
    result = routing.simulate_route(copy.deepcopy(stops), [], [], manual_order)
    returned_ids = [s["id"] for s in result["stops"]]
    assert returned_ids == manual_order


def test_optimize_order_by_window(routing):
    stops = [
        {"id": "A", "address": "addrA", "window_start": "10:00", "lat": 0.0, "lon": 0.0},
        {"id": "B", "address": "addrB", "window_start": "08:00", "lat": 0.0, "lon": 1.0},
        {"id": "C", "address": "addrC", "window_start": "09:00", "lat": 0.0, "lon": 2.0},
    ]
    result = routing.simulate_route(copy.deepcopy(stops), [], [], [], optimize=True)
    returned_ids = [s["id"] for s in result["stops"]]
    assert returned_ids == ["B", "C", "A"]
