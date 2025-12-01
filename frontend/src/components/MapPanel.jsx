import { useEffect, useMemo, useRef, useState } from "react";
import { GoogleMap, Marker, Polyline, DirectionsRenderer, useJsApiLoader } from "@react-google-maps/api";

const containerStyle = { width: "100%", height: "400px", borderRadius: 8, overflow: "hidden", border: "1px solid #ddd" };

const MAP_LIBRARIES = ["marker"];

export default function MapPanel({ stops = [], path = [], originAddress, destinationAddress, onRouteStats }) {
  const [directions, setDirections] = useState(null);
  const [advSupported, setAdvSupported] = useState(false);
  const mapRef = useRef(null);
  const advMarkersRef = useRef([]);
  const { isLoaded, loadError } = useJsApiLoader({
    googleMapsApiKey: import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "",
    libraries: MAP_LIBRARIES,
  });

  const markers = useMemo(
    () =>
      stops
        .filter((s) => s.lat !== undefined && s.lon !== undefined)
        .map((s, idx) => ({
          id: `${s.id}-${idx}`,
          position: { lat: Number(s.lat), lng: Number(s.lon) },
          label: `${idx + 1}`,
          title: `${idx + 1}. ${s.customer_name}`,
        })),
    [stops]
  );

  const center = markers[0]?.position || { lat: 39.5, lng: -98.35 };

  const pathLatLng = path
    .filter((p) => Array.isArray(p) && p.length === 2)
    .map(([lat, lon]) => ({ lat: Number(lat), lng: Number(lon) }));

  useEffect(() => {
    if (!isLoaded || !(window.google && window.google.maps)) return;
    if (mapRef.current && markers.length) {
      const bounds = new window.google.maps.LatLngBounds();
      markers.forEach((m) => bounds.extend(m.position));
      mapRef.current.panTo(markers[0].position);
      mapRef.current.fitBounds(bounds, 80);
    }
  }, [markers, isLoaded]);

  useEffect(() => {
    if (!isLoaded || !mapRef.current || !(window.google && window.google.maps)) return;
    const renderMarkers = async () => {
      try {
        const { AdvancedMarkerElement } = await window.google.maps.importLibrary("marker");
        const { PinElement } = await window.google.maps.importLibrary("marker");
        // Clear old markers
        advMarkersRef.current.forEach((mk) => mk && mk.map && mk.setMap(null));
        advMarkersRef.current = [];
        markers.forEach((m) => {
          const pin = new PinElement({
            glyph: m.label,
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
        setAdvSupported(true);
      } catch (e) {
        setAdvSupported(false);
      }
    };
    renderMarkers();
    return () => {
      advMarkersRef.current.forEach((mk) => mk && mk.map && mk.setMap(null));
      advMarkersRef.current = [];
      setAdvSupported(false);
    };
  }, [markers, isLoaded]);

  useEffect(() => {
    setDirections(null);
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
      <GoogleMap
        center={center}
        zoom={10}
        mapContainerStyle={{ width: "100%", height: "100%" }}
        onLoad={(map) => (mapRef.current = map)}
      >
        {!advSupported &&
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
