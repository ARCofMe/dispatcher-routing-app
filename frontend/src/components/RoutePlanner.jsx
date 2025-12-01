import { useMemo, useState } from "react";
import { fetchRoutePreview, simulateRoute, commitRoute } from "../api/client";
import StopList from "./StopList";
import MetricsPanel from "./MetricsPanel";
import MapPanel from "./MapPanel";

export default function RoutePlanner({ techId }) {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [route, setRoute] = useState(null);
  const [originAddress, setOriginAddress] = useState("");
  const [destinationAddress, setDestinationAddress] = useState("");
  const [routeStats, setRouteStats] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchRoutePreview(techId, date, originAddress || undefined, destinationAddress || undefined);
      setRoute(data);
      setRouteStats({ waypointMiles: data?.metrics?.total_distance_miles });
      setStatus("Preview loaded");
    } catch (err) {
      setError("Failed to load preview");
    } finally {
      setLoading(false);
    }
  };

  const handleReorder = async (stops) => {
    if (!stops || stops.length === 0) return;
    const manual_order = stops.map((s) => s.id);
    setRoute((prev) => (prev ? { ...prev, stops } : { stops, metrics: null }));
    try {
      const updated = await simulateRoute({
        existing_assignments: stops,
        added_stops: [],
        removed_ids: [],
        manual_order,
        origin: originAddress || undefined,
        destination: destinationAddress || undefined,
      });
      setRoute(updated);
      setRouteStats({ waypointMiles: updated?.metrics?.total_distance_miles });
      setStatus("Simulation updated");
    } catch (err) {
      setError("Unable to simulate route");
    }
  };

  const commit = async () => {
    if (!route) return;
    setLoading(true);
    setError("");
    try {
      await commitRoute({
        tech_id: techId,
        date,
        manual_order: route.stops.map((s) => s.id),
        ordered_stops: route.stops,
        origin: originAddress || undefined,
        destination: destinationAddress || undefined,
      });
      setStatus("Route committed to BlueFolder");
    } catch (err) {
      setError("Commit failed");
    } finally {
      setLoading(false);
    }
  };

  const path = useMemo(() => route?.path || [], [route]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 12,
          background: "rgba(30, 41, 59, 0.65)",
          border: "1px solid rgba(148, 163, 184, 0.25)",
          borderRadius: 12,
          padding: 14,
        }}
      >
        <label style={{ display: "flex", flexDirection: "column", gap: 6, color: "#cbd5e1", fontSize: 13 }}>
          Date
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6, color: "#cbd5e1", fontSize: 13 }}>
          Origin (optional)
          <input
            type="text"
            placeholder="e.g. 123 Main St"
            value={originAddress}
            onChange={(e) => setOriginAddress(e.target.value)}
            style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6, color: "#cbd5e1", fontSize: 13 }}>
          Destination (optional)
          <input
            type="text"
            placeholder="e.g. Home base"
            value={destinationAddress}
            onChange={(e) => setDestinationAddress(e.target.value)}
            style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
          />
        </label>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
          <button
            onClick={load}
            disabled={loading}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #3b82f6",
              background: "#2563eb",
              color: "#e2e8f0",
              cursor: "pointer",
              minWidth: 90,
            }}
          >
            {loading ? "Loading…" : "Load"}
          </button>
          <button
            onClick={commit}
            disabled={!route || loading}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #10b981",
              background: "#059669",
              color: "#e2e8f0",
              cursor: route ? "pointer" : "not-allowed",
              minWidth: 90,
            }}
          >
            Commit
          </button>
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 10, color: "#cbd5e1", fontSize: 13 }}>
          {status && <span style={{ color: "#34d399" }}>{status}</span>}
          {error && <span style={{ color: "#f87171" }}>{error}</span>}
        </div>
      </div>
      {route && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div>
            <StopList stops={route.stops} onReorder={handleReorder} />
            <MetricsPanel metrics={route.metrics} routeStats={routeStats} />
          </div>
          <MapPanel
            stops={route.stops}
            path={path}
            originAddress={originAddress || undefined}
            destinationAddress={destinationAddress || undefined}
            onRouteStats={(stats) => setRouteStats((prev) => ({ ...prev, ...stats }))}
          />
        </div>
      )}
    </div>
  );
}
