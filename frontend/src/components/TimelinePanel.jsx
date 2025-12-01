export default function TimelinePanel({ stops }) {
  if (!stops || !stops.length) return null;
  return (
    <div style={{ border: "1px solid #334155", borderRadius: 12, background: "rgba(15,23,42,0.5)", padding: 12, color: "#e2e8f0" }}>
      <div style={{ marginBottom: 8, color: "#cbd5e1", fontSize: 13 }}>Timeline</div>
      <div style={{ display: "grid", gap: 8 }}>
        {stops.map((s, idx) => {
          const windowLabel = s.window_start && s.window_end ? `${s.window_start}-${s.window_end}` : "Anytime";
          const late = s.eta && s.window_end && s.eta > s.window_end;
          return (
            <div key={`${s.id}-${idx}`} style={{ display: "grid", gridTemplateColumns: "40px 1fr", gap: 10, alignItems: "center" }}>
              <div style={{ fontWeight: 600 }}>{idx + 1}</div>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                  <span>{s.customer_name}</span>
                  <span style={{ color: late ? "#f87171" : "#93c5fd" }}>{s.eta || "ETA—"}</span>
                </div>
                <div style={{ height: 6, background: "#0f172a", borderRadius: 6, marginTop: 4, position: "relative" }}>
                  <div
                    style={{
                      position: "absolute",
                      left: 0,
                      top: 0,
                      height: "100%",
                      width: "100%",
                      background: late ? "linear-gradient(90deg,#f87171,#ef4444)" : "linear-gradient(90deg,#38bdf8,#2563eb)",
                      opacity: 0.4,
                      borderRadius: 6,
                    }}
                  />
                </div>
                <div style={{ fontSize: 12, color: late ? "#f87171" : "#cbd5e1" }}>Window: {windowLabel}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
