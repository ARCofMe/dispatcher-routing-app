import { useEffect, useMemo, useState } from "react";
import { fetchRoutePreview, simulateRoute, commitRoute } from "../api/client";
import StopList from "./StopList";
import MetricsPanel from "./MetricsPanel";
import MapPanel from "./MapPanel";
import TimelinePanel from "./TimelinePanel";

export default function RoutePlanner({ techId }) {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [route, setRoute] = useState(null);
  const [originAddress, setOriginAddress] = useState("");
  const [destinationAddress, setDestinationAddress] = useState("");
  const [routeStats, setRouteStats] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [shareStatus, setShareStatus] = useState("");
  const [hideCompleted, setHideCompleted] = useState(false);
  const [prevMetrics, setPrevMetrics] = useState(null);
  const [newStop, setNewStop] = useState({ name: "", address: "", duration_minutes: 30, window_start: "", window_end: "" });
  const draftKey = useMemo(() => `route-draft-${techId}-${date}`, [techId, date]);
  const cacheKey = useMemo(() => `route-cache-${techId}-${date}`, [techId, date]);
  const [validation, setValidation] = useState({ late: 0 });

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchRoutePreview(techId, date, originAddress || undefined, destinationAddress || undefined);
      setRoute(data);
      setPrevMetrics(data?.metrics || null);
      setRouteStats({ waypointMiles: data?.metrics?.total_distance_miles });
      setStatus("Preview loaded");
      localStorage.setItem(
        cacheKey,
        JSON.stringify({ route: data, originAddress, destinationAddress })
      );
    } catch (err) {
      const cached = localStorage.getItem(cacheKey);
      if (cached) {
        try {
          const parsed = JSON.parse(cached);
          setRoute(parsed.route);
          setOriginAddress(parsed.originAddress || "");
          setDestinationAddress(parsed.destinationAddress || "");
          setRouteStats({ waypointMiles: parsed.route?.metrics?.total_distance_miles });
          setStatus("Loaded cached route");
        } catch {
          setError("Failed to load preview");
        }
      } else {
        setError("Failed to load preview");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReorder = async (stops) => {
    if (!stops || stops.length === 0) return;
    const manual_order = stops.map((s) => s.id);
    setRoute((prev) => (prev ? { ...prev, stops } : { stops, metrics: null }));
    try {
      if (route?.metrics) setPrevMetrics(route.metrics);
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
      localStorage.setItem(
        cacheKey,
        JSON.stringify({ route: updated, originAddress, destinationAddress })
      );
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
  const legs = useMemo(() => {
    const hv = (a, b) => {
      const toRad = (v) => (v * Math.PI) / 180;
      const [lat1, lon1] = a;
      const [lat2, lon2] = b;
      const dlon = toRad(lon2 - lon1);
      const dlat = toRad(lat2 - lat1);
      const la1 = toRad(lat1);
      const la2 = toRad(lat2);
      const h = Math.sin(dlat / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dlon / 2) ** 2;
      return 2 * 6371 * Math.asin(Math.sqrt(h)); // km
    };
    const res = [];
    for (let i = 1; i < path.length; i++) {
      const km = hv(path[i - 1], path[i]);
      res.push({ index: i, km, miles: km * 0.621371 });
    }
    return res;
  }, [path]);

  const handleStatusChange = (index, nextStatus) => {
    setRoute((prev) => {
      if (!prev) return prev;
      const updatedStops = prev.stops.map((s, idx) => (idx === index ? { ...s, status: nextStatus } : s));
      return { ...prev, stops: updatedStops };
    });
  };

  const handleEditStop = async (index, updatedFields) => {
    setRoute((prev) => {
      if (!prev) return prev;
      const updatedStops = prev.stops.map((s, idx) => (idx === index ? { ...s, ...updatedFields } : s));
      return { ...prev, stops: updatedStops };
    });
    if (route?.metrics) setPrevMetrics(route.metrics);
    try {
      const updated = await simulateRoute({
        existing_assignments: route.stops.map((s, idx) => (idx === index ? { ...s, ...updatedFields } : s)),
        added_stops: [],
        removed_ids: [],
        manual_order: route.stops.map((s) => s.id),
        origin: originAddress || undefined,
        destination: destinationAddress || undefined,
      });
      setRoute(updated);
      setRouteStats({ waypointMiles: updated?.metrics?.total_distance_miles });
      setStatus("Stop updated");
      localStorage.setItem(
        cacheKey,
        JSON.stringify({ route: updated, originAddress, destinationAddress })
      );
    } catch {
      setError("Unable to update stop");
    }
  };

  const saveDraft = () => {
    if (!route) return;
    localStorage.setItem(
      draftKey,
      JSON.stringify({ route, originAddress, destinationAddress })
    );
    setStatus("Draft saved");
  };

  const loadDraft = () => {
    const raw = localStorage.getItem(draftKey);
    if (!raw) {
      setStatus("No draft found");
      return;
    }
    try {
      const data = JSON.parse(raw);
      setRoute(data.route);
      setOriginAddress(data.originAddress || "");
      setDestinationAddress(data.destinationAddress || "");
      setRouteStats({ waypointMiles: data.route?.metrics?.total_distance_miles });
      setStatus("Draft loaded");
    } catch {
      setStatus("Draft load failed");
    }
  };

  const buildRouteUrl = () => {
    const parts = [];
    if (originAddress) parts.push(originAddress);
    (route?.stops || []).forEach((s) => parts.push(s.address || `${s.lat},${s.lon}`));
    if (destinationAddress) parts.push(destinationAddress);
    const filtered = parts.filter(Boolean);
    return "https://www.google.com/maps/dir/" + filtered.map(encodeURIComponent).join("/");
  };

  const copyRoute = async () => {
    try {
      await navigator.clipboard.writeText(buildRouteUrl());
      setShareStatus("Route link copied");
      setTimeout(() => setShareStatus(""), 2000);
    } catch (err) {
      setShareStatus("Unable to copy");
    }
  };

  useEffect(() => {
    const handler = (e) => {
      if (e.metaKey || e.ctrlKey) {
        if (e.key.toLowerCase() === "s") {
          e.preventDefault();
          saveDraft();
        }
        if (e.key.toLowerCase() === "c") {
          e.preventDefault();
          copyRoute();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [route, originAddress, destinationAddress]);

  useEffect(() => {
    if (!route?.stops) return;
    const late = route.stops.filter((s) => s.eta && s.window_end && s.eta > s.window_end).length;
    const suggested = [...route.stops].sort((a, b) => {
      const aw = a.window_start || "";
      const bw = b.window_start || "";
      return aw.localeCompare(bw);
    });
    setValidation({ late, suggested });
  }, [route]);

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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <div style={{ color: "#cbd5e1", fontSize: 13 }}>Route stops</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#cbd5e1" }}>
                  <input type="checkbox" checked={hideCompleted} onChange={(e) => setHideCompleted(e.target.checked)} />
                  Hide completed
                </label>
                <button
                  onClick={() => {
                    if (!validation.suggested) return;
                    handleReorder(validation.suggested);
                    setStatus("Suggested order applied");
                  }}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 8,
                    border: "1px solid #475569",
                    background: "rgba(51,65,85,0.6)",
                    color: "#e2e8f0",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  Suggest by window
                </button>
                <button
                  onClick={saveDraft}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 8,
                    border: "1px solid #475569",
                    background: "rgba(51,65,85,0.6)",
                    color: "#e2e8f0",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  Save draft
                </button>
                <button
                  onClick={loadDraft}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 8,
                    border: "1px solid #475569",
                    background: "rgba(51,65,85,0.6)",
                    color: "#e2e8f0",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  Load draft
                </button>
                <button
                  onClick={copyRoute}
                  style={{
                    padding: "6px 10px",
                    borderRadius: 8,
                    border: "1px solid #475569",
                    background: "rgba(51,65,85,0.6)",
                    color: "#e2e8f0",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  Copy route link
                </button>
                {shareStatus && <span style={{ color: "#34d399", fontSize: 12 }}>{shareStatus}</span>}
              </div>
            </div>
            <StopList
              stops={hideCompleted ? route.stops.filter((s) => s.status !== "complete") : route.stops}
              onReorder={handleReorder}
              onStatusChange={handleStatusChange}
              onEditStop={handleEditStop}
            />
            <div style={{ marginTop: 10, padding: 12, borderRadius: 12, border: "1px solid #334155", background: "rgba(30,41,59,0.6)" }}>
              <div style={{ color: "#cbd5e1", marginBottom: 8, fontSize: 13 }}>Add ad-hoc stop</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <input
                  type="text"
                  placeholder="Customer / label"
                  value={newStop.name}
                  onChange={(e) => setNewStop((p) => ({ ...p, name: e.target.value }))}
                  style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
                />
                <input
                  type="text"
                  placeholder="Address"
                  value={newStop.address}
                  onChange={(e) => setNewStop((p) => ({ ...p, address: e.target.value }))}
                  style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
                />
                <input
                  type="number"
                  placeholder="Duration (mins)"
                  value={newStop.duration_minutes}
                  onChange={(e) => setNewStop((p) => ({ ...p, duration_minutes: Number(e.target.value) || 0 }))}
                  style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
                />
                <div style={{ display: "flex", gap: 8 }}>
                  <input
                    type="time"
                    value={newStop.window_start}
                    onChange={(e) => setNewStop((p) => ({ ...p, window_start: e.target.value }))}
                    style={{ flex: 1, padding: "8px 10px", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
                  />
                  <input
                    type="time"
                    value={newStop.window_end}
                    onChange={(e) => setNewStop((p) => ({ ...p, window_end: e.target.value }))}
                    style={{ flex: 1, padding: "8px 10px", borderRadius: 8, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
                  />
                </div>
              </div>
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={async () => {
                    if (!newStop.address) return;
                    const stop = {
                      id: `adhoc-${Date.now()}`,
                      customer_name: newStop.name || "Ad-hoc Stop",
                      address: newStop.address,
                      duration_minutes: newStop.duration_minutes || 30,
                      window_start: newStop.window_start || undefined,
                      window_end: newStop.window_end || undefined,
                    };
                    const updatedStops = [...(route?.stops || []), stop];
                    setRoute((prev) => (prev ? { ...prev, stops: updatedStops } : { stops: updatedStops, metrics: prev?.metrics }));
                    setPrevMetrics(route?.metrics || null);
                    try {
                      const updated = await simulateRoute({
                        existing_assignments: updatedStops,
                        added_stops: [stop],
                        removed_ids: [],
                        manual_order: updatedStops.map((s) => s.id),
                        origin: originAddress || undefined,
                        destination: destinationAddress || undefined,
                      });
                      setRoute(updated);
                      setRouteStats({ waypointMiles: updated?.metrics?.total_distance_miles });
                      setStatus("Ad-hoc stop added");
                      localStorage.setItem(
                        cacheKey,
                        JSON.stringify({ route: updated, originAddress, destinationAddress })
                      );
                    } catch (err) {
                      setError("Unable to add stop");
                    }
                  }}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 8,
                    border: "1px solid #475569",
                    background: "#1d4ed8",
                    color: "#e2e8f0",
                    cursor: "pointer",
                  }}
                >
                  Add stop
                </button>
              </div>
            </div>
          </div>
          <div style={{ display: "grid", gap: 12 }}>
            <MapPanel
              stops={route.stops}
              path={path}
              originAddress={originAddress || undefined}
              destinationAddress={destinationAddress || undefined}
              onRouteStats={(stats) => setRouteStats((prev) => ({ ...prev, ...stats }))}
            />
            <MetricsPanel metrics={route.metrics} routeStats={routeStats} prevMetrics={prevMetrics} legs={legs} />
            <TimelinePanel stops={route.stops} />
            <div style={{ border: "1px solid #334155", borderRadius: 12, padding: 12, background: "rgba(15,23,42,0.5)", color: "#e2e8f0" }}>
              <div style={{ fontSize: 13, color: "#cbd5e1", marginBottom: 6 }}>Share to tech</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  onClick={() => {
                    const body = encodeURIComponent(`Route for ${date}:\n${buildRouteUrl()}\nFirst stop ETA: ${route?.stops?.[0]?.eta || "N/A"}`);
                    window.open(`mailto:?subject=Route for ${date}&body=${body}`, "_blank");
                  }}
                  style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #475569", background: "rgba(51,65,85,0.6)", color: "#e2e8f0", cursor: "pointer", fontSize: 12 }}
                >
                  Email route
                </button>
                <button
                  onClick={() => {
                    const text = encodeURIComponent(`Route for ${date}: ${buildRouteUrl()} (First ETA: ${route?.stops?.[0]?.eta || "N/A"})`);
                    window.open(`sms:?&body=${text}`, "_blank");
                  }}
                  style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #475569", background: "rgba(51,65,85,0.6)", color: "#e2e8f0", cursor: "pointer", fontSize: 12 }}
                >
                  SMS route
                </button>
                {validation.late > 0 && <span style={{ color: "#fbbf24", fontSize: 12 }}>{validation.late} stops past window</span>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
