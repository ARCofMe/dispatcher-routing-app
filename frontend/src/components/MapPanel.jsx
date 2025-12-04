import { useEffect, useMemo, useRef, useState } from "react";
import { GoogleMap, Marker, Polyline, DirectionsRenderer, useJsApiLoader } from "@react-google-maps/api";

const containerStyle = { width: "100%", height: "400px", borderRadius: 8, overflow: "hidden", border: "1px solid #ddd" };

const MAP_LIBRARIES = ["marker"];
const MAP_ID = import.meta.env.VITE_GOOGLE_MAP_ID;
const MAP_IDS = MAP_ID ? [MAP_ID] : [];

export default function MapPanel({ stops = [], path = [], originAddress, destinationAddress, onRouteStats }) {
  const [directions, setDirections] = useState(null);
  const [directionsError, setDirectionsError] = useState("");
  const [advSupported, setAdvSupported] = useState(false);
  const [advCheckDone, setAdvCheckDone] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const mapIdAppliedRef = useRef(false);
  const [geoCache, setGeoCache] = useState({});
  const mapRef = useRef(null);
  const advMarkersRef = useRef([]);
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "",
    libraries: MAP_LIBRARIES,
    mapIds: MAP_IDS,
  });

  useEffect(() => {
    if (!isLoaded || !(window.google && window.google.maps)) return;
    const geocoder = new window.google.maps.Geocoder();
    stops.forEach((s) => {
      const latMissing = s.lat == null || Number.isNaN(Number(s.lat));
      const lonMissing = s.lon == null || Number.isNaN(Number(s.lon));
      if ((latMissing || lonMissing) && s.address && !geoCache[s.id]) {
        geocoder.geocode({ address: s.address }, (results, status) => {
          if (status === "OK" && results && results[0]) {
            const loc = results[0].geometry.location;
            setGeoCache((prev) => ({ ...prev, [s.id]: { lat: loc.lat(), lng: loc.lng() } }));
          } else {
            // Surface failed lookups so missing markers are discoverable.
            console.warn("Geocode failed for stop", s.id, s.address, status);
          }
        });
      }
    });
  }, [stops, isLoaded, geoCache]);

  const markers = useMemo(
    () =>
      stops
        .map((s, idx) => {
          const lat = s.lat ?? geoCache[s.id]?.lat;
          const lon = s.lon ?? geoCache[s.id]?.lng;
          if (lat == null || lon == null || Number.isNaN(Number(lat)) || Number.isNaN(Number(lon))) return null;
          return {
            id: `${s.id}-${idx}`,
            position: { lat: Number(lat), lng: Number(lon) },
            label: `${idx + 1}`,
            title: `${idx + 1}. ${s.customer_name}`,
          };
        })
        .filter(Boolean),
    [stops, geoCache]
  );

  const center = markers[0]?.position || { lat: 39.5, lng: -98.35 };

  const pathLatLng = path
    .filter((p) => Array.isArray(p) && p.length === 2)
    .map(([lat, lon]) => ({ lat: Number(lat), lng: Number(lon) }));

  const missingStops = useMemo(
    () =>
      stops.filter(
        (s) =>
          ((s.lat == null || Number.isNaN(Number(s.lat))) ||
            (s.lon == null || Number.isNaN(Number(s.lon)))) &&
          !geoCache[s.id]
      ),
    [stops, geoCache]
  );

  const clearAdvMarkers = () => {
    advMarkersRef.current.forEach((mk) => {
      if (!mk) return;
      if (typeof mk.setMap === "function") {
        mk.setMap(null);
      } else if ("map" in mk) {
        mk.map = null;
      }
    });
    advMarkersRef.current = [];
  };

  useEffect(() => {
    if (!isLoaded || !mapReady || !(window.google && window.google.maps) || !mapRef.current) return;
    if (markers.length) {
      const bounds = new window.google.maps.LatLngBounds();
      markers.forEach((m) => bounds.extend(m.position));
      mapRef.current.panTo(markers[0].position);
      mapRef.current.fitBounds(bounds, 80);
    }
  }, [markers, isLoaded, mapReady]);

  useEffect(() => {
    if (!isLoaded || !mapReady || !mapRef.current || !(window.google && window.google.maps)) {
      setAdvSupported(false);
      return;
    }
    if (MAP_IDS.length && !mapIdAppliedRef.current) {
      setAdvSupported(false);
      setAdvCheckDone(true);
      clearAdvMarkers();
      return;
    }
    let cancelled = false;
    const renderMarkers = async () => {
      try {
        const { AdvancedMarkerElement } = await window.google.maps.importLibrary("marker");
        const { PinElement } = await window.google.maps.importLibrary("marker");
        if (!AdvancedMarkerElement || !PinElement || !mapRef.current) {
          if (!cancelled) {
            setAdvSupported(false);
            setAdvCheckDone(true);
          }
          return;
        }
        // Clear old markers
        clearAdvMarkers();
        if (markers.length) {
          markers.forEach((m) => {
            const pin = new PinElement({
              glyphText: m.label,
              background: "#2563eb",
              glyphColor: "#e2e8f0",
            });
            const adv = new AdvancedMarkerElement({
              position: m.position,
              map: mapRef.current,
              title: m.title,
              content: pin.element,
            });
            advMarkersRef.current.push(adv);
          });
        }
        if (!cancelled) {
          setAdvSupported(true);
          setAdvCheckDone(true);
        }
      } catch (e) {
        if (!cancelled) {
          setAdvSupported(false);
          setAdvCheckDone(true);
        }
      }
    };
    renderMarkers();
    return () => {
      cancelled = true;
      clearAdvMarkers();
      setAdvSupported(false);
      setAdvCheckDone(false);
    };
  }, [markers, isLoaded, mapReady]);

  useEffect(() => {
    setDirections(null);
    setDirectionsError("");
    if (!isLoaded || markers.length < 2) return;
    if (!(window.google && window.google.maps)) return;

    const origin = originAddress?.trim() || markers[0].position;
    const destination = destinationAddress?.trim() || markers[markers.length - 1].position;
    const waypoints = markers.slice(1, -1).map((m) => ({ location: m.position, stopover: true }));

    const service = new window.google.maps.DirectionsService();
    service.route(
      {
        origin,
        destination,
        waypoints,
        travelMode: window.google.maps.TravelMode.DRIVING,
        avoidFerries: true,
        optimizeWaypoints: false,
      },
      (result, status) => {
        if (status === "OK") {
          setDirections(result);
          const legs = result.routes?.[0]?.legs || [];
          const meters = legs.reduce((sum, leg) => sum + (leg.distance?.value || 0), 0);
          if (onRouteStats && meters) {
            onRouteStats({ routeMiles: (meters / 1609.344).toFixed(2) });
          }
        } else {
          setDirections(null);
          setDirectionsError(status || "Unable to build route");
          console.warn("Directions request failed", status, { origin, destination, waypoints });
        }
      }
    );
  }, [markers, isLoaded, originAddress, destinationAddress]);

  if (loadError) {
    return <div style={{ height: 400, border: "1px solid #ddd", borderRadius: 8 }}>Unable to load Google Maps.</div>;
  }

  if (!isLoaded) {
    return <div style={{ height: 400, border: "1px solid #ddd", borderRadius: 8 }}>Loading map…</div>;
  }

  return (
    <div style={containerStyle}>
      {directionsError && (
        <div style={{ position: "absolute", zIndex: 2, margin: 8, padding: "6px 8px", background: "rgba(239,68,68,0.9)", color: "#fff", borderRadius: 8, border: "1px solid #b91c1c", fontSize: 12 }}>
          Route unavailable ({directionsError}). Check addresses/origin/destination.
        </div>
      )}
      {missingStops.length > 0 && (
        <div style={{ position: "absolute", zIndex: 2, margin: 8, padding: "6px 8px", background: "rgba(15,23,42,0.9)", color: "#fbbf24", borderRadius: 8, border: "1px solid #f59e0b", fontSize: 12 }}>
          {missingStops.length} stop(s) missing coordinates — check address or geocode limits.
        </div>
      )}
      <GoogleMap
        center={center}
        zoom={10}
        mapContainerStyle={{ width: "100%", height: "100%" }}
        mapId={MAP_ID || undefined}
        onLoad={(map) => {
          mapRef.current = map;
          if (MAP_ID) {
            map.setOptions({ mapId: MAP_ID });
            mapIdAppliedRef.current = !!map.get("mapId");
          } else {
            mapIdAppliedRef.current = false;
          }
          setMapReady(true);
        }}
      >
        {advCheckDone && !advSupported &&
          markers.map((m) => (
            <Marker key={m.id} position={m.position} label={m.label} title={m.title} />
          ))}
        {directions ? (
          <DirectionsRenderer
            directions={directions}
            options={{ suppressMarkers: true, polylineOptions: { strokeColor: "#2563eb", strokeWeight: 4, strokeOpacity: 0.8 } }}
          />
        ) : (
          pathLatLng.length > 1 && <Polyline path={pathLatLng} options={{ strokeColor: "#2563eb", strokeWeight: 4, strokeOpacity: 0.8 }} />
        )}
      </GoogleMap>
    </div>
  );
}
