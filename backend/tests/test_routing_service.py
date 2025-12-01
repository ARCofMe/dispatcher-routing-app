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
