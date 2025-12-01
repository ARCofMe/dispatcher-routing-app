import { useState } from "react";
import TechSelector from "./components/TechSelector";
import RoutePlanner from "./components/RoutePlanner";

const pageStyle = {
  minHeight: "100vh",
  background: "linear-gradient(135deg, #0f172a 0%, #111827 50%, #0b1220 100%)",
  color: "#e2e8f0",
  padding: "32px 24px",
  fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
};

const shellStyle = {
  maxWidth: 1200,
  margin: "0 auto",
  background: "rgba(15, 23, 42, 0.65)",
  border: "1px solid rgba(148, 163, 184, 0.25)",
  boxShadow: "0 30px 80px rgba(0,0,0,0.35)",
  borderRadius: 18,
  padding: 24,
  backdropFilter: "blur(6px)",
};

export default function App() {
  const [techId, setTechId] = useState(null);
  return (
    <div style={pageStyle}>
      <div style={shellStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
          <div>
            <div style={{ fontSize: 13, textTransform: "uppercase", letterSpacing: 1.5, color: "#94a3b8" }}>Dispatcher Routing</div>
            <h1 style={{ margin: "4px 0 0", fontSize: 28, color: "#e2e8f0" }}>Daily Route Planner</h1>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 13, color: "#94a3b8" }}>Technician</span>
            <TechSelector value={techId} onChange={setTechId} />
          </div>
        </div>
        <div style={{ marginTop: 18 }}>
          {techId ? (
            <RoutePlanner techId={techId} />
          ) : (
            <div style={{ color: "#cbd5e1", fontSize: 15 }}>Select a technician to load their route.</div>
          )}
        </div>
      </div>
    </div>
  );
}
