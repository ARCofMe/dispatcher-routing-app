export default function MetricsPanel({metrics, routeStats}) {
  if(!metrics) return null;
  const waypointMiles = routeStats?.waypointMiles ?? (metrics.total_distance_miles ?? (metrics.total_distance_km*0.621371).toFixed(2));
  const totalRouteMiles = routeStats?.routeMiles ?? waypointMiles;

  return (
    <div style={{ marginTop: 12, padding: 14, borderRadius: 12, border: "1px solid #334155", background: "rgba(30,41,59,0.6)", color: "#e2e8f0" }}>
      <h3 style={{ margin: "0 0 8px", color: "#cbd5e1" }}>Metrics</h3>
      <div style={{ display: "grid", gap: 6, fontSize: 14 }}>
        <div><strong style={{ color: "#93c5fd" }}>Route</strong> (origin → destination): {totalRouteMiles} miles</div>
        <div><strong style={{ color: "#93c5fd" }}>Stops</strong> distance: {waypointMiles} miles</div>
        <div><strong style={{ color: "#93c5fd" }}>Travel</strong> time: {metrics.total_travel_minutes} mins</div>
        {metrics.estimated_completion && <div><strong style={{ color: "#93c5fd" }}>ETA finish</strong>: {metrics.estimated_completion}</div>}
      </div>
    </div>
  );
}
