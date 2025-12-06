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
            import googlemaps  # type: ignore

            key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("VITE_GOOGLE_MAPS_API_KEY")
            if key:
                return googlemaps.Client(key=key)
        except Exception:
            pass
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

    def preview_route(self, stops: Sequence[dict], origin: str = None, destination: str = None, optimize: bool = False):
        # Ensure coordinates early so optimization can use distance.
        hydrated = self._ensure_coordinates(list(stops))
        ordered = self._optimize_order(hydrated, optimize=optimize, origin=origin, destination=destination)
        metrics, enriched_stops = self._build_metrics(ordered, origin=origin, destination=destination)
        return {"stops": enriched_stops, "metrics": metrics, "path": self._build_path(enriched_stops, origin=origin, destination=destination)}

    def simulate_route(self, existing_assignments: List[dict], added_stops: List[dict], removed_ids: List[str], manual_order: List[str], origin: str = None, destination: str = None, optimize: bool = False):
        """
        Produce a simulated route. When the optimized-routing-extension is available, call it here and return its output.
        The manual_order parameter is respected to keep dispatcher drag/drop sequencing intact.
        """
        # Merge added/removed stops before ordering.
        filtered = [s for s in existing_assignments if str(s.get("id")) not in set(map(str, removed_ids))]
        combined = filtered + added_stops

        ordered = self._apply_manual_order(combined, manual_order)
        ordered = self._ensure_coordinates(ordered)
        ordered = self._optimize_order(ordered, optimize=optimize, origin=origin, destination=destination)

        metrics, enriched_stops = self._build_metrics(ordered, origin=origin, destination=destination)
        return {"stops": enriched_stops, "metrics": metrics, "path": self._build_path(enriched_stops, origin=origin, destination=destination)}

    def _optimize_order(self, stops: List[dict], optimize: bool = False, origin: str = None, destination: str = None) -> List[dict]:
        """
        Use the optimized-routing-extension to reorder if desired.
        To avoid losing duplicate stops, we currently preserve the incoming list when optimization is unavailable.
        """
        if not optimize:
            return stops

        # If multiple distinct windows exist, honor window ordering first and optimize within each window.
        unique_windows = {s.get("window_start") for s in stops if s.get("window_start")}
        if unique_windows and len(unique_windows) > 1:
            try:
                # Geocode origin/destination once for anchoring buckets.
                origin_coord = None
                dest_coord = None
                try:
                    if origin:
                        origin_coord = self._geocode(origin)
                    if destination:
                        dest_coord = self._geocode(destination)
                except Exception:
                    origin_coord = None
                    dest_coord = None

                ordered: List[dict] = []
                current_coord = origin_coord
                sorted_windows = sorted(unique_windows)
                for idx, ws in enumerate(sorted_windows):
                    bucket = [s for s in stops if s.get("window_start") == ws]
                    is_last = idx == len(sorted_windows) - 1
                    nn_bucket = self._nearest_neighbor(
                        bucket,
                        fix_endpoints=False,
                        start_coord=current_coord,
                        dest_coord=dest_coord if is_last else None,
                    ) or bucket
                    ordered.extend(nn_bucket)
                    # Update anchor to last stop in this bucket for next bucket.
                    try:
                        last = nn_bucket[-1]
                        if last.get("lat") is not None and last.get("lon") is not None:
                            current_coord = (float(last["lat"]), float(last["lon"]))
                    except Exception:
                        pass
                return ordered
            except Exception:
                pass

        # Attempt Directions-based optimization.
        gmaps_key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("VITE_GOOGLE_MAPS_API_KEY")
        if gmaps_key:
            # Attempt full-route optimization via Google Maps (server-side key) if available.
            try:
                import googlemaps  # type: ignore

                if len(stops) >= 2:
                    client = googlemaps.Client(key=gmaps_key)

                    def stop_address(st):
                        if st.get("address"):
                            return st["address"]
                        lat = st.get("lat")
                        lon = st.get("lon")
                        if lat is not None and lon is not None:
                            return f"{lat},{lon}"
                        return None

                    addresses = [stop_address(s) for s in stops]
                    if all(addresses):
                        orig = origin or addresses[0]
                        dest = destination or addresses[-1]
                        waypoint_addrs = addresses[1:-1]
                        directions = client.directions(orig, dest, waypoints=waypoint_addrs, optimize_waypoints=True)
                        if directions and "waypoint_order" in directions[0]:
                            order = directions[0]["waypoint_order"]
                            middle = [stops[1:-1][i] for i in order] if len(stops) > 2 else []
                            reordered = [stops[0]] + middle + [stops[-1]]
                            return reordered
            except Exception:
                pass

        # Distance-based fallback.
        origin_coord = None
        dest_coord = None
        try:
            if origin:
                origin_coord = self._geocode(origin)
            if destination:
                dest_coord = self._geocode(destination)
        except Exception:
            origin_coord = None
            dest_coord = None

        nn = self._nearest_neighbor(
            stops,
            fix_endpoints=bool(origin_coord or dest_coord),
            start_coord=origin_coord,
            dest_coord=dest_coord,
        )
        if nn:
            return nn

        # Last resort, keep incoming.
        return stops

    def _nearest_neighbor(
        self,
        stops: List[dict],
        fix_endpoints: bool = False,
        start_coord: tuple = None,
        dest_coord: tuple = None,
    ) -> List[dict]:
        """Simple nearest-neighbor path using lat/lon.
        Tries multiple start candidates and picks the shortest path; if fix_endpoints/dest provided, anchor the finish."""
        coords = []
        for s in stops:
            lat = s.get("lat")
            lon = s.get("lon")
            if lat is not None and lon is not None:
                coords.append((float(lat), float(lon)))
            else:
                coords.append(None)

        if not any(c is not None for c in coords):
            return []

        indices = list(range(len(stops)))
        with_coords = [i for i in indices if coords[i] is not None]
        if not with_coords:
            return []

        def dist_to_start(idx):
            lat, lon = coords[idx]
            if start_coord:
                return self._haversine(start_coord[1], start_coord[0], lon, lat)
            return 0.0

        def dist_to_dest(idx):
            lat, lon = coords[idx]
            if dest_coord:
                return self._haversine(lon, lat, dest_coord[1], dest_coord[0])
            return 0.0

        start_candidates = sorted(with_coords, key=dist_to_start)[:3] or with_coords[:3]

        def build_route(start_idx):
            end_idx = min(with_coords, key=dist_to_dest) if (fix_endpoints and dest_coord) else None
            if end_idx == start_idx:
                end_idx = None

            current = start_idx
            remaining = set(with_coords)
            order = [current]
            remaining.discard(current)
            if end_idx is not None:
                remaining.discard(end_idx)

            while remaining:
                clat, clon = coords[current]

                def hav(idx):
                    lat, lon = coords[idx]
                    return self._haversine(clon, clat, lon, lat)

                next_idx = min(remaining, key=hav)
                remaining.remove(next_idx)
                order.append(next_idx)
                current = next_idx

            if end_idx is not None:
                order.append(end_idx)

            # Append any without coords at the end in original order.
            order.extend([i for i in indices if i not in order])
            return order

        def route_cost(order):
            total = 0.0
            prev = None
            if start_coord is not None:
                prev = (start_coord[0], start_coord[1])
            for idx in order:
                lat, lon = coords[idx] if coords[idx] is not None else (None, None)
                if prev and lat is not None and lon is not None:
                    total += self._haversine(prev[1], prev[0], lon, lat)
                if lat is not None and lon is not None:
                    prev = (lat, lon)
            if dest_coord and prev:
                total += self._haversine(prev[1], prev[0], dest_coord[1], dest_coord[0])
            return total

        best_order = None
        best_cost = float("inf")
        for cand in start_candidates:
            order = build_route(cand)
            cost = route_cost(order)
            if cost < best_cost:
                best_cost = cost
                best_order = order

        return [stops[i] for i in best_order] if best_order else []

    def _ensure_coordinates(self, stops: List[dict]) -> List[dict]:
        """
        Populate lat/lon for stops missing coordinates using geopy (Nominatim) with a small cache.
        This keeps map/metrics usable even when BlueFolder data lacks geocodes.
        """
        enriched = []
        for stop in stops:
            if stop.get("lat") is not None and stop.get("lon") is not None:
                try:
                    lat_f = float(stop.get("lat"))
                    lon_f = float(stop.get("lon"))
                    if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                        stop = dict(stop)
                        stop["lat"], stop["lon"] = lat_f, lon_f
                        enriched.append(stop)
                        continue
                except Exception:
                    pass
            # geocode if needed
            coords = self._geocode(stop.get("address"))
            if coords:
                lat_f, lon_f = coords
                if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                    stop = dict(stop)
                    stop["lat"], stop["lon"] = lat_f, lon_f
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
            loc = None
            # googlemaps client
            try:
                import googlemaps  # type: ignore
                if isinstance(self._geocoder, googlemaps.Client):
                    res = self._geocoder.geocode(address)
                    if res:
                        geom = res[0].get("geometry", {}).get("location", {})
                        lat = geom.get("lat")
                        lng = geom.get("lng")
                        if lat is not None and lng is not None:
                            loc = (lat, lng)
            except Exception:
                pass
            # geopy fallback
            if loc is None and hasattr(self._geocoder, "geocode"):
                geo_res = self._geocoder.geocode(address, timeout=5)
                if geo_res and hasattr(geo_res, "latitude") and hasattr(geo_res, "longitude"):
                    loc = (geo_res.latitude, geo_res.longitude)
            if loc:
                if self._geocode_cache:
                    self._geocode_cache.set(address, loc)
                return loc
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
                coords.append([geocoded[0], geocoded[1]])
        for stop in stops:
            lat = stop.get("lat")
            lon = stop.get("lon")
            if lat is not None and lon is not None:
                coords.append([lat, lon])
        if destination:
            geocoded = self._geocode(destination)
            if geocoded:
                coords.append([geocoded[0], geocoded[1]])
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
