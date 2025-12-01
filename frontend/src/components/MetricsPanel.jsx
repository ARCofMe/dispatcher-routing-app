export default function MetricsPanel({metrics, routeStats, prevMetrics}) {
  if(!metrics) return null;
  const waypointMiles = routeStats?.waypointMiles ?? (metrics.total_distance_miles ?? (metrics.total_distance_km*0.621371).toFixed(2));
  const totalRouteMiles = routeStats?.routeMiles ?? waypointMiles;
  const deltaMiles = prevMetrics && prevMetrics.total_distance_miles !== undefined ? (totalRouteMiles - prevMetrics.total_distance_miles).toFixed(2) : null;
  const deltaTime = prevMetrics && prevMetrics.total_travel_minutes !== undefined ? (metrics.total_travel_minutes - prevMetrics.total_travel_minutes) : null;

  return (
    <div style={{ marginTop: 12, padding: 14, borderRadius: 12, border: "1px solid #334155", background: "rgba(30,41,59,0.6)", color: "#e2e8f0" }}>
      <h3 style={{ margin: "0 0 8px", color: "#cbd5e1" }}>Metrics</h3>
      <div style={{ display: "grid", gap: 6, fontSize: 14 }}>
        <div><strong style={{ color: "#93c5fd" }}>Route</strong> (origin → destination): {totalRouteMiles} miles {deltaMiles && <span style={{ color: deltaMiles >= 0 ? "#fbbf24" : "#34d399" }}>({deltaMiles >=0 ? "+" : ""}{deltaMiles})</span>}</div>
        <div><strong style={{ color: "#93c5fd" }}>Stops</strong> distance: {waypointMiles} miles</div>
        <div><strong style={{ color: "#93c5fd" }}>Travel</strong> time: {metrics.total_travel_minutes} mins {deltaTime !== null && <span style={{ color: deltaTime >= 0 ? "#fbbf24" : "#34d399" }}>({deltaTime >=0 ? "+" : ""}{deltaTime}m)</span>}</div>
        {metrics.estimated_completion && <div><strong style={{ color: "#93c5fd" }}>ETA finish</strong>: {metrics.estimated_completion}</div>}
      </div>
    </div>
  );
}
