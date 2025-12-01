import os
import sys
import math
from datetime import datetime, time, timedelta
from typing import List, Sequence


def _maybe_extend_sys_path():
    """Allow importing the local optimized-routing-extension without publishing it."""
    default_path = "/home/ner0tic/Documents/Projects/ARCoM/optimized-routing-extension"
    candidate = os.getenv("ROUTING_EXTENSION_PATH", default_path)
    if candidate and candidate not in sys.path:
        sys.path.append(candidate)


class RoutingService:
    """
    Bridge to the optimized routing engine.
    Replace the placeholder ordering/metrics with calls into the optimized-routing-extension once available.
    """

    AVERAGE_SPEED_KMH = 40  # Safe default for ETA calculations when a routing engine is unavailable.
    START_TIME = time(8, 0)

    def __init__(self):
        _maybe_extend_sys_path()
        self._routing_helpers = self._init_routing_helpers()
        self._geocoder = self._init_geocoder()
        self._geocode_cache = self._init_cache()

    def _init_routing_helpers(self):
        try:
            from optimized_routing.routing import bluefolder_to_routestops, dedupe_stops  # type: ignore
            from optimized_routing.manager.base import ServiceWindow  # type: ignore

            return {
                "bluefolder_to_routestops": bluefolder_to_routestops,
                "dedupe_stops": dedupe_stops,
                "ServiceWindow": ServiceWindow,
            }
        except Exception:
            return None

    def _init_geocoder(self):
        try:
            from geopy.geocoders import Nominatim  # type: ignore

            return Nominatim(user_agent="dispatcher-routing-app")
        except Exception:
            return None

    def _init_cache(self):
        try:
            from optimized_routing.utils.cache_manager import CacheManager  # type: ignore

            return CacheManager("geocode", ttl_minutes=60)
        except Exception:
            return None

    def preview_route(self, stops: Sequence[dict], origin: str = None, destination: str = None):
        ordered = self._ensure_coordinates(self._optimize_order(list(stops)))
        metrics, enriched_stops = self._build_metrics(ordered, origin=origin, destination=destination)
        return {"stops": enriched_stops, "metrics": metrics, "path": self._build_path(enriched_stops, origin=origin, destination=destination)}

    def simulate_route(self, existing_assignments: List[dict], added_stops: List[dict], removed_ids: List[str], manual_order: List[str], origin: str = None, destination: str = None):
        """
        Produce a simulated route. When the optimized-routing-extension is available, call it here and return its output.
        The manual_order parameter is respected to keep dispatcher drag/drop sequencing intact.
        """
        # Merge added/removed stops before ordering.
        filtered = [s for s in existing_assignments if str(s.get("id")) not in set(map(str, removed_ids))]
        combined = filtered + added_stops

        ordered = self._apply_manual_order(combined, manual_order)
        ordered = self._optimize_order(ordered)
        ordered = self._ensure_coordinates(ordered)

        metrics, enriched_stops = self._build_metrics(ordered, origin=origin, destination=destination)
        return {"stops": enriched_stops, "metrics": metrics, "path": self._build_path(enriched_stops, origin=origin, destination=destination)}

    def _optimize_order(self, stops: List[dict]) -> List[dict]:
        """
        Use the optimized-routing-extension to reorder if desired.
        To avoid losing duplicate stops, we currently preserve the incoming list when optimization is unavailable.
        """
        helpers = self._routing_helpers
        if not helpers:
            return stops
        try:
            # Keep order as-is for now to avoid deduping overlapping stops with the same address/label.
            return stops
        except Exception:
            return stops

    def _ensure_coordinates(self, stops: List[dict]) -> List[dict]:
        """
        Populate lat/lon for stops missing coordinates using geopy (Nominatim) with a small cache.
        This keeps map/metrics usable even when BlueFolder data lacks geocodes.
        """
        enriched = []
        for stop in stops:
            if stop.get("lat") is not None and stop.get("lon") is not None:
                enriched.append(stop)
                continue
            coords = self._geocode(stop.get("address"))
            if coords:
                stop = dict(stop)
                stop["lon"], stop["lat"] = coords  # geopy returns (lon, lat)
            enriched.append(stop)
        return enriched

    def _geocode(self, address: str):
        if not address or not self._geocoder:
            return None
        try:
            if self._geocode_cache:
                cached = self._geocode_cache.get(address)
                if cached:
                    return cached
            loc = self._geocoder.geocode(address, timeout=5)
            if loc:
                coords = (loc.longitude, loc.latitude)
                if self._geocode_cache:
                    self._geocode_cache.set(address, coords)
                return coords
        except Exception:
            return None
        return None

    def _apply_manual_order(self, stops: List[dict], manual_order: List[str]):
        if not manual_order:
            return stops
        order_lookup = {str(stop_id): idx for idx, stop_id in enumerate(manual_order)}
        return sorted(stops, key=lambda s: order_lookup.get(str(s.get("id")), len(manual_order)))

    def _build_path(self, stops: Sequence[dict], origin: str = None, destination: str = None):
        coords = []
        # Optionally geocode origin/destination into the path so distance includes them.
        if origin:
            geocoded = self._geocode(origin)
            if geocoded:
                coords.append([geocoded[1], geocoded[0]])
        for stop in stops:
            lat = stop.get("lat")
            lon = stop.get("lon")
            if lat is not None and lon is not None:
                coords.append([lat, lon])
        if destination:
            geocoded = self._geocode(destination)
            if geocoded:
                coords.append([geocoded[1], geocoded[0]])
        return coords

    def _build_metrics(self, stops: Sequence[dict], origin: str = None, destination: str = None):
        total_distance_km = 0.0
        total_travel_minutes = 0.0
        path = self._build_path(stops, origin=origin, destination=destination)
        for i in range(1, len(path)):
            segment_km = self._haversine(path[i - 1][1], path[i - 1][0], path[i][1], path[i][0])
            total_distance_km += segment_km
            total_travel_minutes += (segment_km / self.AVERAGE_SPEED_KMH) * 60

        eta_start = datetime.combine(datetime.today(), self.START_TIME)
        eta_cursor = eta_start
        enriched_stops = []
        for idx, stop in enumerate(stops):
            travel_minutes = 0
            if idx < len(path) and idx > 0 and len(path[idx - 1]) == 2 and len(path[idx]) == 2:
                travel_minutes = (self._haversine(path[idx - 1][1], path[idx - 1][0], path[idx][1], path[idx][0]) / self.AVERAGE_SPEED_KMH) * 60
            eta_cursor += timedelta(minutes=travel_minutes)
            stop_with_eta = dict(stop)
            stop_with_eta["eta"] = eta_cursor.strftime("%H:%M")
            duration = int(stop_with_eta.get("duration_minutes") or 0)
            eta_cursor += timedelta(minutes=duration)
            enriched_stops.append(stop_with_eta)

        total_distance_miles = total_distance_km * 0.621371
        metrics = {
            "total_distance_km": round(total_distance_km, 2),
            "total_distance_miles": round(total_distance_miles, 2),
            "total_travel_minutes": int(total_travel_minutes),
            "estimated_completion": eta_cursor.strftime("%H:%M"),
            "includes_origin_destination": bool(origin or destination),
        }
        return metrics, enriched_stops

    @staticmethod
    def _haversine(lon1, lat1, lon2, lat2):
        """Calculate the great-circle distance between two points on the Earth."""
        lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Earth radius in km
        return c * r
