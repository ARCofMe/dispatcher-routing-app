import { useEffect, useMemo, useRef, useState } from "react";
import { GoogleMap, Marker, Polyline, DirectionsRenderer, useJsApiLoader } from "@react-google-maps/api";
import { MapContainer, TileLayer, Marker as LeafletMarker, Polyline as LeafletPolyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const MAP_HEIGHT = 400;
const containerStyle = {
  width: "100%",
  borderRadius: 8,
  border: "1px solid #ddd",
  background: "rgba(15,23,42,0.6)",
  display: "flex",
  flexDirection: "column",
  gap: 8,
  padding: 8,
};

const MAP_LIBRARIES = ["marker"];
const MAP_ID = import.meta.env.VITE_GOOGLE_MAP_ID;
const MAP_IDS = MAP_ID ? [MAP_ID] : [];
const DISABLE_DIRECTIONS = String(import.meta.env.VITE_DISABLE_DIRECTIONS || "").toLowerCase() === "true";
const USE_LEAFLET = String(import.meta.env.VITE_USE_LEAFLET || "").toLowerCase() === "true";

const EQUIPMENT_META = {
  rf: { label: "Refrigerator", bg: "#2563eb", marker: "blue" },
  fr: { label: "Freezer", bg: "#7c3aed", marker: "purple" },
  wt: { label: "Washer (Top)", bg: "#0d9488", marker: "green" },
  wf: { label: "Washer (Front)", bg: "#06b6d4", marker: "ltblue" },
  wdc: { label: "Washer/Dryer Combo", bg: "#f97316", marker: "orange" },
  lc: { label: "Laundry Center", bg: "#f59e0b", marker: "yellow" },
  dw: { label: "Dishwasher", bg: "#64748b", marker: "gray" },
  eo: { label: "Electric Oven", bg: "#9333ea", marker: "purple" },
  go: { label: "Gas Oven", bg: "#ef4444", marker: "red" },
  dr: { label: "Electric Dryer", bg: "#22c55e", marker: "green" },
  gdr: { label: "Gas Dryer", bg: "#16a34a", marker: "green" },
  wo: { label: "Wall Oven", bg: "#8b5cf6", marker: "purple" },
  im: { label: "Ice Maker", bg: "#0ea5e9", marker: "ltblue" },
  tv: { label: "TV", bg: "#e11d48", marker: "pink" },
  mw: { label: "Microwave", bg: "#a855f7", marker: "purple" },
  otr: { label: "OTR Microwave", bg: "#f472b6", marker: "pink" },
  ct: { label: "Cooktop", bg: "#fb7185", marker: "pink" },
  other: { label: "Other", bg: "#475569", marker: "gray" },
};

const resolveEquip = (stop) => {
  const codes = ["rf", "fr", "wt", "wf", "wdc", "lc", "dw", "eo", "go", "dr", "gdr", "wo", "im", "tv", "mw", "otr", "ct"];
  const candidates = [];
  const pushVal = (val) => {
    if (!val) return;
    if (Array.isArray(val)) {
      val.forEach(pushVal);
      return;
    }
    if (typeof val === "object") {
      Object.values(val).forEach(pushVal);
      return;
    }
    candidates.push(String(val));
  };

  pushVal(stop?.equipment_type);
  pushVal(stop?.equipment);
  pushVal(stop?.equipment_name);
  pushVal(stop?.equipmentName);
  pushVal(stop?.equipment_label);
  pushVal(stop?.equipmentLabel);
  pushVal(stop?.equipment_display);
  pushVal(stop?.equipmentDisplay);
  pushVal(stop?.equipmentToService);
  pushVal(stop?.category);
  pushVal(stop?.equipment_id);
  pushVal(stop?.customer_name);
  pushVal(stop?.subject);

  const rawJoined = candidates.join(" | ");
  const tokens = rawJoined
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);

  // Exact token match only to avoid matching codes inside words (e.g., "freeport" -> "fr").
  const found = tokens.find((t) => codes.includes(t));
  if (found) return found;

  // Allow tokens that start with a code followed by digits (e.g., "dr1") if present.
  const starts = tokens.find((t) => codes.some((c) => t.startsWith(c)));
  if (starts) {
    const code = codes.find((c) => starts.startsWith(c));
    if (code) return code;
  }

  return "other";
};

const buildIcon = (label, color) =>
  L.divIcon({
    className: "",
    html: `<div style="
      background:${color};
      color:#f8fafc;
      width:26px;
      height:26px;
      border-radius:12px;
      display:flex;
      align-items:center;
      justify-content:center;
      font-size:12px;
      font-weight:700;
      border:1px solid rgba(15,23,42,0.15);
      box-shadow:0 2px 6px rgba(0,0,0,0.25);
    ">${label}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });

function FitBounds({ markers }) {
  const map = useMap();
  useEffect(() => {
    if (!map || !markers?.length) return;
    const bounds = L.latLngBounds(markers.map((m) => m.position));
    map.fitBounds(bounds, { padding: [40, 40] });
  }, [map, markers]);
  return null;
}

const DARK_MAP_STYLE = [
  { elementType: "geometry", stylers: [{ color: "#1f2937" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#9ca3af" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#111827" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#111827" }] },
  { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#1f2937" }] },
  { featureType: "road", elementType: "labels.text.fill", stylers: [{ color: "#e5e7eb" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#0ea5e9" }] },
  { featureType: "poi", stylers: [{ visibility: "off" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
];

export default function MapPanel({ stops = [], path = [], originAddress, destinationAddress, onRouteStats, optimizeWaypoints = false, theme = "dark" }) {
  const [directions, setDirections] = useState(null);
  const [directionsError, setDirectionsError] = useState("");
  const [advSupported, setAdvSupported] = useState(false);
  const [advCheckDone, setAdvCheckDone] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const mapIdAppliedRef = useRef(false);
  const [geoCache, setGeoCache] = useState({});
  const mapRef = useRef(null);
  const advMarkersRef = useRef([]);
  const lastAdvSigRef = useRef("");
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
          const equipment = resolveEquip(s);
          return {
            id: `${s.id}-${idx}`,
            position: { lat: Number(lat), lng: Number(lon) },
            label: `${idx + 1}`,
            title: `${idx + 1}. ${s.customer_name}`,
            equipment,
          };
        })
        .filter(Boolean),
    [stops, geoCache]
  );

  const center = markers[0]?.position || { lat: 39.5, lng: -98.35 };
  const hasEndpoints = Boolean(originAddress || destinationAddress);

  const pathLatLng = path
    .filter((p) => Array.isArray(p) && p.length === 2)
    .map(([lat, lon]) => ({ lat: Number(lat), lng: Number(lon) }))
    .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng) && p.lat <= 90 && p.lat >= -90 && p.lng <= 180 && p.lng >= -180);
  const startPos = pathLatLng[0];
  const endPos = pathLatLng.length > 1 ? pathLatLng[pathLatLng.length - 1] : undefined;

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

  const mapOptions = useMemo(() => {
    // When a mapId is provided, styling must come from the cloud console, so skip styles here.
    const opts = MAP_ID ? {} : { styles: theme === "dark" ? DARK_MAP_STYLE : undefined };
    return opts;
  }, [theme]);

  const advSignature = useMemo(() => {
    const markerSig = markers
      .map((m) => `${m.id}:${m.position.lat.toFixed(6)},${m.position.lng.toFixed(6)}:${m.equipment}`)
      .join("|");
    const startSig = startPos ? `S:${startPos.lat.toFixed(6)},${startPos.lng.toFixed(6)}` : "S:na";
    const endSig = endPos ? `E:${endPos.lat.toFixed(6)},${endPos.lng.toFixed(6)}` : "E:na";
    return `${markerSig}||${startSig}||${endSig}`;
  }, [markers, startPos, endPos]);

  const legendItems = useMemo(() => {
    const seen = new Set();
    markers.forEach((m) => seen.add(m.equipment || "other"));
    return Array.from(seen)
      .map((code) => ({ code, meta: EQUIPMENT_META[code] || EQUIPMENT_META.other }))
      .sort((a, b) => a.meta.label.localeCompare(b.meta.label));
  }, [markers]);

  useEffect(() => {
    if (!isLoaded || !mapReady || !(window.google && window.google.maps)) return;
    if (DISABLE_DIRECTIONS || pathLatLng.length < 2) {
      setDirections(null);
      setDirectionsError("");
      return;
    }
    const svc = new window.google.maps.DirectionsService();
    const origin = pathLatLng[0];
    const destination = pathLatLng[pathLatLng.length - 1];
    const waypoints = pathLatLng.slice(1, -1).map((loc) => ({ location: loc, stopover: true }));
    svc.route(
      {
        origin,
        destination,
        waypoints,
        travelMode: window.google.maps.TravelMode.DRIVING,
        optimizeWaypoints: false, // honor backend/manual order
      },
      (result, status) => {
        if (status === "OK" && result?.routes?.length) {
          setDirections(result);
          const legs = result.routes[0].legs || [];
          const meters = legs.reduce((sum, leg) => sum + (leg.distance?.value || 0), 0);
          const seconds = legs.reduce((sum, leg) => sum + (leg.duration?.value || 0), 0);
          onRouteStats?.({ distanceMiles: meters / 1609.344, durationMinutes: seconds / 60 });
          setDirectionsError("");
        } else {
          setDirections(null);
          setDirectionsError(status);
        }
      }
    );
  }, [isLoaded, mapReady, pathLatLng, onRouteStats]);

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
    lastAdvSigRef.current = "";
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
        if (lastAdvSigRef.current === advSignature) {
          if (!cancelled) {
            setAdvSupported(true);
            setAdvCheckDone(true);
          }
          return;
        }
        // Clear old markers
        clearAdvMarkers();
        if (markers.length) {
          markers.forEach((m) => {
            const colors = EQUIPMENT_META[m.equipment] || EQUIPMENT_META.other;
            const pin = new PinElement({
              glyphText: m.label,
              background: colors.bg,
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
        // Start / end markers with distinct colors when advanced markers are available
        if (hasEndpoints && endPos) {
          const endPin = new PinElement({
            glyphText: "F",
            background: "#ef4444",
            glyphColor: "#f8fafc",
          });
          advMarkersRef.current.push(
            new AdvancedMarkerElement({
              position: endPos,
              map: mapRef.current,
              title: "Finish",
              content: endPin.element,
            })
          );
        }
        if (!cancelled) {
          lastAdvSigRef.current = advSignature;
          setAdvSupported(advMarkersRef.current.length > 0);
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
    };
  }, [markers, isLoaded, mapReady, startPos, endPos, advSignature]);

  useEffect(() => {
    return () => {
      clearAdvMarkers();
    };
  }, []);

  useEffect(() => {
    setDirectionsError("");
  }, [markers, isLoaded, originAddress, destinationAddress]);

  if (loadError) {
    return <div style={{ height: 400, border: "1px solid #ddd", borderRadius: 8 }}>Unable to load Google Maps.</div>;
  }

  if (!isLoaded) {
    return <div style={{ height: 400, border: "1px solid #ddd", borderRadius: 8 }}>Loading map…</div>;
  }

  if (USE_LEAFLET) {
    const finishIcon = buildIcon("F", "#ef4444");
    return (
      <div style={containerStyle}>
        <div style={{ position: "relative", width: "100%", height: MAP_HEIGHT, borderRadius: 8, overflow: "hidden" }}>
          <MapContainer center={center} zoom={10} style={{ width: "100%", height: "100%" }}>
            <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <FitBounds markers={markers} />
            {markers.map((m) => (
              <LeafletMarker key={m.id} position={m.position} icon={buildIcon(m.label, EQUIPMENT_META[m.equipment]?.bg || "#2563eb")} />
            ))}
            {hasEndpoints && endPos && <LeafletMarker position={endPos} icon={finishIcon} />}
            {pathLatLng.length > 1 && <LeafletPolyline positions={pathLatLng} pathOptions={{ color: "#2563eb", weight: 4, opacity: 0.85 }} />}
          </MapContainer>
        </div>
        {legendItems.length > 0 && (
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", padding: "6px 8px", borderRadius: 8, background: "rgba(15,23,42,0.75)", color: "#e2e8f0", border: "1px solid rgba(148,163,184,0.3)", fontSize: 11 }}>
            {legendItems.map(({ code, meta }) => (
              <div key={code} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 999, background: meta.bg }} />
                <span>{meta.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={{ position: "relative", width: "100%", height: MAP_HEIGHT, borderRadius: 8, overflow: "hidden" }}>
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
          options={mapOptions}
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
        {(!advSupported || advMarkersRef.current.length === 0) && (
          <>
            {hasEndpoints && endPos && (
              <Marker
                position={endPos}
                label="F"
                title="Finish"
                icon={{ url: "http://maps.google.com/mapfiles/ms/icons/red-dot.png" }}
              />
            )}
            {advCheckDone &&
              markers.map((m) => (
                <Marker
                  key={m.id}
                  position={m.position}
                  label={m.label}
                  title={m.title}
                  icon={{ url: `http://maps.google.com/mapfiles/ms/icons/${(EQUIPMENT_META[m.equipment]?.marker || "blue")}-dot.png` }}
                />
              ))}
          </>
        )}
        {directions ? (
          <DirectionsRenderer
            directions={directions}
            options={{
              suppressMarkers: true,
              polylineOptions: { strokeColor: "#2563eb", strokeWeight: 5, strokeOpacity: 0.85 },
            }}
          />
        ) : (
          pathLatLng.length > 1 && <Polyline path={pathLatLng} options={{ strokeColor: "#2563eb", strokeWeight: 4, strokeOpacity: 0.8 }} />
        )}
        </GoogleMap>
      </div>
      {legendItems.length > 0 && (
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", padding: "6px 8px", borderRadius: 8, background: "rgba(15,23,42,0.75)", color: "#e2e8f0", border: "1px solid rgba(148,163,184,0.3)", fontSize: 11 }}>
          {legendItems.map(({ code, meta }) => (
            <div key={code} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 10, height: 10, borderRadius: 999, background: meta.bg }} />
              <span>{meta.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
