import os
import sys
import math
import json
import time as time_module
from datetime import datetime, time, timedelta
from typing import List, Sequence
from urllib.parse import urlparse


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
        self._geoapify_key = os.getenv("GEOAPIFY_API_KEY")
        self._geoapify_only_mode = str(os.getenv("GEOAPIFY_ONLY_MODE") or "true").lower() in ("1", "true", "yes")
        self._use_geoapify_matrix = bool(self._geoapify_key)
        self._routing_helpers = self._init_routing_helpers()
        self._geocoder = self._init_geocoder()
        self._geocode_cache = self._init_cache()
        self._routing_api_cache = self._init_routing_api_cache()
        self._geocode_backoff_until = 0.0
        self._geocode_last_request_at = 0.0
        self._geocode_min_interval_seconds = float(os.getenv("GEOCODE_MIN_INTERVAL_SECONDS") or 0.25)
        self._logger = None
        self._osrm_urls = {
            'ME': os.getenv("OSRM_MAINE_URL"),
            'NH': os.getenv("OSRM_NH_URL"),
            'MA': os.getenv("OSRM_MA_URL")
        }
        self._allow_osrm = not self._geoapify_only_mode and any(self._osrm_urls.values())
        self._respect_windows = str(os.getenv("OPTIMIZE_RESPECT_WINDOWS") or "true").lower() in ("1", "true", "yes")

    def _get_osrm_url(self, lat: float, lon: float) -> str:
        """Determine OSRM URL based on lat/lon bounding boxes for New England states."""
        if 43 <= lat <= 47 and -71 <= lon <= -67:
            return self._osrm_urls.get('ME')
        elif 42.7 <= lat <= 45.3 and -72.6 <= lon <= -70.6:
            return self._osrm_urls.get('NH')
        elif 41.2 <= lat <= 42.9 and -73.5 <= lon <= -69.9:
            return self._osrm_urls.get('MA')
        return None

    def _get_traffic_multiplier(self) -> float:
        """Return a traffic multiplier based on current time of day.
        Basic implementation: higher during rush hours, lower during off-peak.
        """
        now = datetime.now()
        hour = now.hour

        # Morning rush hour: 7-9 AM
        if 7 <= hour <= 9:
            return 1.4  # 40% increase
        # Evening rush hour: 4-6 PM
        elif 16 <= hour <= 18:
            return 1.3  # 30% increase
        # Midday: 10 AM - 3 PM
        elif 10 <= hour <= 15:
            return 1.1  # 10% increase
        # Off-peak: 7 PM - 6 AM
        else:
            return 1.0  # No increase

    def _log(self, event: str, data: dict):
        try:
            import logging
            if not self._logger:
                self._logger = logging.getLogger("routing")
            self._logger.info(f"{event}: {data}")
        except Exception:
            # Avoid breaking flow on logging errors in tests.
            pass

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
        if self._geoapify_key:
            return None
        try:
            import googlemaps  # type: ignore

            key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("VITE_GOOGLE_MAPS_API_KEY")
            disable_google = str(os.getenv("DISABLE_GMAPS_GEOCODER") or "").lower() in ("1", "true", "yes")
            if key and not disable_google:
                return googlemaps.Client(key=key)
        except Exception:
            pass
        try:
            # Try Geoapify if available (may not be in all geopy versions)
            geoapify_key = os.getenv("GEOAPIFY_API_KEY")
            if geoapify_key:
                try:
                    from geopy.geocoders import Geoapify  # type: ignore
                    return Geoapify(api_key=geoapify_key, timeout=5)
                except ImportError:
                    # Geoapify not available in this geopy version
                    pass
        except Exception:
            pass
        try:
            from geopy.geocoders import Nominatim  # type: ignore

            enable_nominatim = str(os.getenv("ENABLE_NOMINATIM_GEOCODER") or "").lower() in ("1", "true", "yes")
            # Allow overriding the Nominatim endpoint (e.g., self-hosted) via NOMINATIM_URL.
            nominatim_domain = os.getenv("NOMINATIM_URL")
            if nominatim_domain:
                parsed = urlparse(nominatim_domain)
                domain = parsed.netloc or parsed.path or nominatim_domain
                return Nominatim(user_agent="dispatcher-routing-app", domain=domain)
            if enable_nominatim:
                return Nominatim(user_agent="dispatcher-routing-app", timeout=5)
        except Exception:
            return None
        return None

    def _init_cache(self):
        try:
            from optimized_routing.utils.cache_manager import CacheManager  # type: ignore

            ttl_minutes = int(os.getenv("GEOCODE_CACHE_TTL_MINUTES") or str(30 * 24 * 60))
            return CacheManager("geocode", ttl_minutes=ttl_minutes)
        except Exception:
            return None

    def _init_routing_api_cache(self):
        try:
            from optimized_routing.utils.cache_manager import CacheManager  # type: ignore

            return CacheManager("routing_api", ttl_minutes=15)
        except Exception:
            return None

    def preview_route(self, stops: Sequence[dict], origin: str = None, destination: str = None, optimize: bool = False):
        # Ensure coordinates early so optimization can use distance.
        hydrated = self._ensure_coordinates(list(stops))
        self._log("route_preview_input", {"count": len(hydrated), "optimize": optimize, "origin": origin, "destination": destination})
        ordered = self._optimize_order(hydrated, optimize=optimize, origin=origin, destination=destination)
        metrics, enriched_stops, path = self._build_metrics(ordered, origin=origin, destination=destination)
        return {"stops": enriched_stops, "metrics": metrics, "path": path}

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

        metrics, enriched_stops, path = self._build_metrics(ordered, origin=origin, destination=destination)
        return {"stops": enriched_stops, "metrics": metrics, "path": path}

    def _optimize_order(self, stops: List[dict], optimize: bool = False, origin: str = None, destination: str = None) -> List[dict]:
        """
        Use the optimized-routing-extension to reorder if desired.
        To avoid losing duplicate stops, we currently preserve the incoming list when optimization is unavailable.
        """
        if not optimize:
            return stops

        # If multiple distinct windows exist, optionally honor window ordering first and optimize within each window.
        unique_windows = {s.get("window_start") for s in stops if s.get("window_start")}
        if self._respect_windows and unique_windows and len(unique_windows) > 1:
            try:
                # Skip geocoding origin/destination for now to avoid rate limits
                origin_coord = None
                dest_coord = None
                # try:
                #     if origin:
                #         origin_coord = self._geocode(origin)
                #     if destination:
                #         dest_coord = self._geocode(destination)
                # except Exception:
                #     origin_coord = None
                #     dest_coord = None

                ordered: List[dict] = []
                current_coord = origin_coord
                sorted_windows = sorted(unique_windows)
                for idx, ws in enumerate(sorted_windows):
                    bucket = [s for s in stops if s.get("window_start") == ws]
                    bucket_matrix = self._geoapify_matrix(bucket) if self._use_geoapify_matrix else None
                    if self._use_geoapify_matrix:
                        try:
                            self._log("geoapify_bucket_matrix", {"window": ws, "size": len(bucket), "has_matrix": bool(bucket_matrix)})
                        except Exception:
                            pass
                    is_last = idx == len(sorted_windows) - 1
                    preferred_start = None
                    if current_coord:
                        try:
                            # pick the bucket stop closest to current_coord
                            coords = [
                                (float(b.get("lat")), float(b.get("lon"))) if b.get("lat") is not None and b.get("lon") is not None else None
                                for b in bucket
                            ]
                            with_coords = [i for i, c in enumerate(coords) if c is not None]
                            if with_coords:
                                def dist(i):
                                    lat, lon = coords[i]
                                    return self._haversine(current_coord[1], current_coord[0], lon, lat)
                                preferred_start = min(with_coords, key=dist)
                        except Exception:
                            preferred_start = None
                    nn_bucket = self._nearest_neighbor(
                        bucket,
                        fix_endpoints=bool(dest_coord and is_last),
                        start_coord=current_coord,
                        dest_coord=dest_coord if is_last else None,
                        distance_matrix=bucket_matrix,
                        preferred_start_idx=preferred_start,
                    ) or bucket
                    ordered.extend(nn_bucket)
                    # Update anchor to last stop in this bucket for next bucket.
                    try:
                        last = nn_bucket[-1]
                        if last.get("lat") is not None and last.get("lon") is not None:
                            current_coord = (float(last["lat"]), float(last["lon"]))
                    except Exception:
                        pass
                self._log("opt_window_result", {"count": len(ordered)})
                return ordered
            except Exception as e:
                self._log("opt_window_error", {"error": str(e)})

        # Attempt Directions-based optimization.
        gmaps_key = None
        if not self._geoapify_only_mode and str(os.getenv("DISABLE_GMAPS_DIRECTIONS") or "").lower() not in ("1", "true", "yes"):
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
                            self._log("opt_directions_success", {"order": order, "orig": orig, "dest": dest, "waypoints": len(waypoint_addrs)})
                            return reordered
                        else:
                            self._log("opt_directions_no_order", {"orig": orig, "dest": dest, "waypoints": len(waypoint_addrs)})
            except Exception as e:
                self._log("opt_directions_error", {"error": str(e)})

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

        distance_matrix = None
        if self._use_geoapify_matrix:
            try:
                distance_matrix = self._geoapify_matrix(stops)
                try:
                    self._log("geoapify_route_matrix", {"count": len(stops), "has_matrix": bool(distance_matrix)})
                except Exception:
                    pass
            except Exception:
                distance_matrix = None

        nn = self._nearest_neighbor(
            stops,
            fix_endpoints=bool(origin_coord or dest_coord),
            start_coord=origin_coord,
            dest_coord=dest_coord,
            distance_matrix=distance_matrix,
        )
        if nn:
            self._log("opt_nn_used", {"count": len(nn), "fix_endpoints": bool(origin_coord or dest_coord)})
            return nn

        # Last resort, keep incoming.
        return stops

    def _nearest_neighbor(
        self,
        stops: List[dict],
        fix_endpoints: bool = False,
        start_coord: tuple = None,
        dest_coord: tuple = None,
        distance_matrix: List[List[float]] = None,
        preferred_start_idx: int = None,
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

        def leg_minutes(i, j):
            if distance_matrix and distance_matrix[i][j] is not None:
                return distance_matrix[i][j]
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[j]
            return (self._haversine(lon1, lat1, lon2, lat2) / self.AVERAGE_SPEED_KMH) * 60.0

        if preferred_start_idx is not None and preferred_start_idx in with_coords:
            start_candidates = [preferred_start_idx]
        else:
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
                    if distance_matrix and distance_matrix[current][idx] is not None:
                        return distance_matrix[current][idx]
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
            prev_coord = None
            prev_idx = None
            if start_coord is not None:
                prev_coord = (start_coord[0], start_coord[1])
            for idx in order:
                lat, lon = coords[idx] if coords[idx] is not None else (None, None)
                if prev_coord and lat is not None and lon is not None:
                    if distance_matrix and prev_idx is not None and distance_matrix[prev_idx][idx] is not None:
                        total += distance_matrix[prev_idx][idx]
                    else:
                        total += self._haversine(prev_coord[1], prev_coord[0], lon, lat)
                if lat is not None and lon is not None:
                    prev_coord = (lat, lon)
                    prev_idx = idx
            if dest_coord and prev_coord:
                total += self._haversine(prev_coord[1], prev_coord[0], dest_coord[1], dest_coord[0])
            return total

        # Exact search for small sets to improve quality.
        best_order = None
        best_cost = float("inf")
        from itertools import permutations

        max_exact = 8  # safe upper bound for factorial search
        if len(with_coords) <= max_exact:
            coord_only = with_coords
            # If we have a preferred start index, keep it fixed to anchor the bucket to current_coord.
            if preferred_start_idx is not None and preferred_start_idx in coord_only:
                remaining = [i for i in coord_only if i != preferred_start_idx]
                for perm_tail in permutations(remaining):
                    perm = (preferred_start_idx,) + perm_tail
                    cost = route_cost(list(perm))
                    if cost < best_cost:
                        best_cost = cost
                        best_order = list(perm) + [i for i in indices if i not in perm]
            else:
                if fix_endpoints and start_coord is None:
                    start_candidates = coord_only[:1]
                for perm in permutations(coord_only):
                    cost = route_cost(list(perm))
                    if cost < best_cost:
                        best_cost = cost
                        best_order = list(perm) + [i for i in indices if i not in perm]
        else:
            for cand in start_candidates:
                order = build_route(cand)
                cost = route_cost(order)
                if cost < best_cost:
                    best_cost = cost
                    best_order = order

        # Optional 2-opt refinement on the portion with coordinates.
        def two_opt(order):
            # Only consider indices that have coords; keep no-coord stops at the end as-is.
            coord_indices = [idx for idx in order if coords[idx] is not None]
            if len(coord_indices) < 3:
                return order
            improved = True
            current = coord_indices[:]

            def ordered_cost(ord_list):
                total = 0.0
                prev_coord = None
                prev_idx = None
                if start_coord is not None:
                    prev_coord = (start_coord[0], start_coord[1])
                for idx in ord_list:
                    lat, lon = coords[idx]
                    if prev_coord is not None and prev_idx is not None and distance_matrix and distance_matrix[prev_idx][idx] is not None:
                        total += distance_matrix[prev_idx][idx]
                    elif prev_coord is not None:
                        total += self._haversine(prev_coord[1], prev_coord[0], lon, lat)
                    prev_coord = (lat, lon)
                    prev_idx = idx
                if dest_coord and prev_coord is not None:
                    total += self._haversine(prev_coord[1], prev_coord[0], dest_coord[1], dest_coord[0])
                return total

            best = current
            best_cost_local = ordered_cost(best)
            iter_guard = 0
            max_iter = len(coord_indices) * 10
            while improved and iter_guard < max_iter:
                improved = False
                iter_guard += 1
                n = len(best)
                start_i = 1 if fix_endpoints else 0
                end_i = n - 2 if fix_endpoints else n - 1
                for i in range(start_i, end_i):
                    for j in range(i + 1, n - (1 if fix_endpoints else 0)):
                        if fix_endpoints and (i == 0 or j == n - 1):
                            continue
                        new_path = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                        new_cost = ordered_cost(new_path)
                        if new_cost + 1e-9 < best_cost_local:
                            best = new_path
                            best_cost_local = new_cost
                            improved = True
                if not improved:
                    break

            # Rebuild full order: optimized coords first, then any original no-coord entries in original relative order.
            optimized_with_coords = best
            no_coords = [idx for idx in order if idx not in optimized_with_coords]
            return optimized_with_coords + no_coords

        if best_order:
            refined = two_opt(best_order)
            return [stops[i] for i in refined]
        return []

    def _osrm_route(self, stops: Sequence[dict], origin: str = None, destination: str = None):
        import requests

        # Determine OSRM URL from the first available lat/lon
        osrm_url = None
        # Skip geocoding origin for OSRM URL determination
        # if origin:
        #     geocoded = self._geocode(origin)
        #     if geocoded:
        #         osrm_url = self._get_osrm_url(geocoded[0], geocoded[1])
        if not osrm_url:
            for s in stops:
                lat = s.get("lat")
                lon = s.get("lon")
                if lat is not None and lon is not None:
                    osrm_url = self._get_osrm_url(float(lat), float(lon))
                    break
        if not osrm_url:
            return None

        coords = []
        # Skip geocoding origin for now
        # if origin:
        #     geocoded = self._geocode(origin)
        #     if geocoded:
        #         coords.append(f"{geocoded[1]},{geocoded[0]}")
        for s in stops:
            lat = s.get("lat")
            lon = s.get("lon")
            if lat is None or lon is None:
                return None
            coords.append(f"{lon},{lat}")
        # Skip geocoding destination for now
        # if destination:
        #     geocoded = self._geocode(destination)
        #     if geocoded:
        #         coords.append(f"{geocoded[1]},{geocoded[0]}")

        if len(coords) < 2:
            return None
        url = f"{osrm_url.rstrip('/')}/route/v1/driving/" + ";".join(coords)
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data.get("code") != "Ok":
            return None
        route = data["routes"][0]
        geometry = route.get("geometry", {}).get("coordinates")
        if not geometry:
            return None
        # geometry is [lon, lat]
        return [[lat, lon] for lon, lat in geometry]

    def _osrm_metrics(self, path: Sequence[Sequence[float]]):
        if len(path) < 2:
            return None
        # Determine OSRM URL from the first point in the path
        lat, lon = path[0]
        osrm_url = self._get_osrm_url(lat, lon)
        if not osrm_url:
            return None

        import requests

        coords = [f"{lon},{lat}" for lat, lon in path]
        url = f"{osrm_url.rstrip('/')}/route/v1/driving/" + ";".join(coords)
        params = {"overview": "false", "steps": "false", "annotations": "false"}
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        if data.get("code") != "Ok":
            return None
        route = data["routes"][0]
        dist_m = route.get("distance", 0)
        dur_s = route.get("duration", 0)

        # Apply basic traffic multiplier based on current time
        traffic_multiplier = self._get_traffic_multiplier()
        adjusted_dur_s = dur_s * traffic_multiplier

        return {
            "distance_km": dist_m / 1000.0,
            "travel_minutes": adjusted_dur_s / 60.0,
            "traffic_multiplier": traffic_multiplier,
            "base_duration_minutes": dur_s / 60.0
        }

    def _ensure_coordinates(self, stops: List[dict]) -> List[dict]:
        """
        Populate lat/lon for stops missing coordinates.
        Geocoding is cached aggressively so repeat loads do not keep hitting providers.
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
            coords = self._geocode(stop.get("address"))
            if coords:
                lat_f, lon_f = coords
                if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                    stop = dict(stop)
                    stop["lat"], stop["lon"] = lat_f, lon_f
            enriched.append(stop)
        return enriched

    def _geocode(self, address: str):
        if not address:
            return None
        if time_module.time() < self._geocode_backoff_until:
            return None
        try:
            if self._geocode_cache:
                cached = self._geocode_cache.get(address)
                if cached:
                    return cached
            loc = None
            if self._geoapify_key:
                loc = self._geoapify_geocode(address)
            # googlemaps client
            try:
                import googlemaps  # type: ignore
                if loc is None and self._geocoder and isinstance(self._geocoder, googlemaps.Client):
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
            if loc is None and self._geocoder and hasattr(self._geocoder, "geocode"):
                try:
                    now = time_module.time()
                    wait_s = self._geocode_min_interval_seconds - (now - self._geocode_last_request_at)
                    if wait_s > 0:
                        time_module.sleep(wait_s)
                    geo_res = self._geocoder.geocode(address, timeout=5)
                    self._geocode_last_request_at = time_module.time()
                    if geo_res and hasattr(geo_res, "latitude") and hasattr(geo_res, "longitude"):
                        loc = (geo_res.latitude, geo_res.longitude)
                except Exception as e:
                    # Handle rate limiting and other geocoding errors gracefully
                    if "429" in str(e) or "Too many requests" in str(e):
                        self._geocode_backoff_until = time_module.time() + 300
                        self._log("geocode_rate_limited", {"address": address[:50], "error": str(e)})
                        # Return None to avoid breaking the flow, coordinates will be handled later
                        return None
                    else:
                        self._log("geocode_error", {"address": address[:50], "error": str(e)})
                        return None
            if loc:
                if self._geocode_cache:
                    self._geocode_cache.set(address, loc)
                return loc
        except Exception as e:
            self._log("geocode_unexpected_error", {"address": address[:50], "error": str(e)})
            return None
        return None

    def _geoapify_geocode(self, address: str):
        if not self._geoapify_key:
            return None
        import requests

        cache_key = f"geoapify_geocode:{address.strip().lower()}"
        if self._routing_api_cache:
            cached = self._routing_api_cache.get(cache_key)
            if cached:
                return tuple(cached)

        now = time_module.time()
        wait_s = self._geocode_min_interval_seconds - (now - self._geocode_last_request_at)
        if wait_s > 0:
            time_module.sleep(wait_s)

        resp = requests.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={
                "text": address,
                "limit": 1,
                "format": "json",
                "apiKey": self._geoapify_key,
            },
            timeout=8,
        )
        self._geocode_last_request_at = time_module.time()
        if resp.status_code == 429:
            self._geocode_backoff_until = time_module.time() + 300
            self._log("geoapify_geocode_rate_limited", {"address": address[:50]})
            return None
        if resp.status_code != 200:
            self._log("geoapify_geocode_error", {"address": address[:50], "status": resp.status_code})
            return None

        data = resp.json() if resp.content else {}
        results = data.get("results") if isinstance(data, dict) else None
        if not results:
            return None
        first = results[0]
        lat = first.get("lat")
        lon = first.get("lon")
        if lat is None or lon is None:
            return None
        loc = (float(lat), float(lon))
        if self._routing_api_cache:
            self._routing_api_cache.set(cache_key, list(loc))
        return loc

    def _apply_manual_order(self, stops: List[dict], manual_order: List[str]):
        if not manual_order:
            return stops
        order_lookup = {str(stop_id): idx for idx, stop_id in enumerate(manual_order)}
        return sorted(stops, key=lambda s: order_lookup.get(str(s.get("id")), len(manual_order)))

    def _build_path(self, stops: Sequence[dict], origin: str = None, destination: str = None):
        # Prefer a routed path (OSRM, then Geoapify) when available; fall back to straight coords.
        coords_lonlat = self._collect_lonlat(origin, destination, stops)

        if self._allow_osrm and len(coords_lonlat) >= 2:
            try:
                path = self._osrm_route(stops, origin=origin, destination=destination)
                if path:
                    return path
            except Exception:
                pass

        if self._geoapify_key and len(coords_lonlat) >= 2:
            try:
                routed, _, _ = self._geoapify_route(coords_lonlat)
                if routed:
                    return routed
            except Exception:
                pass

        # Fallback to raw points.
        return [[lat, lon] for lon, lat in coords_lonlat]

    def _build_metrics(self, stops: Sequence[dict], origin: str = None, destination: str = None):
        total_distance_km = 0.0
        total_travel_minutes = 0.0
        traffic_multiplier = 1.0
        base_duration_minutes = 0.0
        coords_lonlat = self._collect_lonlat(origin, destination, stops)
        path = None

        # Try OSRM first for both path and metrics.
        if self._allow_osrm and len(stops) >= 2:
            try:
                path = self._osrm_route(stops, origin=origin, destination=destination)
                osrm_metrics = self._osrm_metrics(path) if path else None
                if osrm_metrics:
                    total_distance_km = osrm_metrics["distance_km"]
                    total_travel_minutes = osrm_metrics["travel_minutes"]
                    traffic_multiplier = osrm_metrics.get("traffic_multiplier", 1.0)
                    base_duration_minutes = osrm_metrics.get("base_duration_minutes", total_travel_minutes)
            except Exception:
                path = None

        # If OSRM unavailable, try Geoapify routing for path + metrics.
        if path is None and self._geoapify_key and len(coords_lonlat) >= 2:
            try:
                routed, dist_km, time_min = self._geoapify_route(coords_lonlat)
                if routed:
                    path = routed
                if dist_km is not None and time_min is not None:
                    total_distance_km = dist_km
                    total_travel_minutes = time_min
            except Exception:
                path = None

        # Fallback: straight-line path and haversine metrics.
        if path is None:
            path = [[lat, lon] for lon, lat in coords_lonlat]

        # If OSRM distance/duration is available, prefer it.
        if total_distance_km == 0.0 and len(path) > 1:
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
            "traffic_multiplier": round(traffic_multiplier, 2),
            "base_duration_minutes": int(base_duration_minutes),
        }
        return metrics, enriched_stops, path

    def _collect_lonlat(self, origin: str, destination: str, stops: Sequence[dict]):
        coords = []
        if origin:
            geocoded = self._geocode(origin)
            if geocoded:
                coords.append((geocoded[1], geocoded[0]))  # lon, lat
        for s in stops:
            if s.get("lat") is not None and s.get("lon") is not None:
                coords.append((float(s["lon"]), float(s["lat"])))
        if destination:
            geocoded = self._geocode(destination)
            if geocoded:
                coords.append((geocoded[1], geocoded[0]))  # lon, lat
        return coords

    def _geoapify_route(self, coords_lonlat: Sequence[tuple]):
        """Return (path_latlon, distance_km, time_minutes) via Geoapify routing."""
        if not self._geoapify_key or len(coords_lonlat) < 2:
            return None, None, None
        import requests

        waypoint_param = "|".join(f"lonlat:{lon},{lat}" for lon, lat in coords_lonlat)
        cache_key = f"geoapify_route:{waypoint_param}"
        if self._routing_api_cache:
            cached = self._routing_api_cache.get(cache_key)
            if cached:
                return tuple(cached)
        params = {
            "waypoints": waypoint_param,
            "mode": "drive",
            "details": "false",
            "apiKey": self._geoapify_key,
        }
        url = "https://api.geoapify.com/v1/routing"
        resp = requests.get(url, params=params, timeout=8)
        if resp.status_code != 200:
            self._log("geoapify_route_error", {"status": resp.status_code, "body": resp.text[:200]})
            return None, None, None
        data = resp.json()
        if not data or "features" not in data or not data["features"]:
            return None, None, None
        feature = data["features"][0]
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates")
        if not coords:
            return None, None, None
        # Geoapify may return a MultiLineString, with one line per leg.
        # Flatten legs into a single path while avoiding duplicate join points.
        if isinstance(coords[0][0], list):
            flat = []
            for idx, leg in enumerate(coords):
                if not leg:
                    continue
                points = leg[1:] if idx > 0 and flat else leg
                flat.extend(points)
            line = flat
        else:
            line = coords
        path_latlon = [[pt[1], pt[0]] for pt in line]
        props = feature.get("properties", {})
        dist_km = props.get("distance") / 1000.0 if props.get("distance") is not None else None
        time_min = props.get("time") / 60.0 if props.get("time") is not None else None
        if self._routing_api_cache:
            self._routing_api_cache.set(cache_key, [path_latlon, dist_km, time_min])
        return path_latlon, dist_km, time_min

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

    def _geoapify_matrix(self, stops: Sequence[dict]):
        """
        Fetch a drive-time matrix from Geoapify so optimization uses road distance/time
        instead of straight-line haversine. Returns a minutes matrix or None on failure.
        """
        if not self._geoapify_key:
            return None
        import requests

        coords = []
        for s in stops:
            if s.get("lat") is None or s.get("lon") is None:
                return None
            coords.append({"location": [float(s["lon"]), float(s["lat"])]})
        if len(coords) < 2:
            return None

        body = {
            "mode": "drive",
            "sources": coords,
            "targets": coords,
        }
        cache_key = f"geoapify_matrix:{json.dumps(body, sort_keys=True, separators=(',', ':'))}"
        if self._routing_api_cache:
            cached = self._routing_api_cache.get(cache_key)
            if cached:
                return cached
        url = f"https://api.geoapify.com/v1/routematrix?apiKey={self._geoapify_key}"
        resp = requests.post(url, json=body, timeout=8)
        if resp.status_code != 200:
            self._log("geoapify_matrix_error", {"status": resp.status_code, "body": resp.text[:200]})
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        matrix = [[None for _ in coords] for _ in coords]
        for item in data.get("sources_to_targets", []):
            if isinstance(item, dict):
                candidates = [item]
            elif isinstance(item, list):
                candidates = [i for i in item if isinstance(i, dict)]
                if not candidates:
                    try:
                        self._log("geoapify_matrix_unexpected_item", {"item": item})
                    except Exception:
                        pass
                    continue
            else:
                try:
                    self._log("geoapify_matrix_unexpected_item", {"item": item})
                except Exception:
                    pass
                continue

            for row in candidates:
                si = row.get("source_index")
                ti = row.get("target_index")
                if si is None or ti is None:
                    continue
                time_s = row.get("time")
                if time_s is not None:
                    matrix[si][ti] = time_s / 60.0
        if self._routing_api_cache:
            self._routing_api_cache.set(cache_key, matrix)
        return matrix
