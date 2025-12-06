import { useState } from "react";
import TechSelector from "./components/TechSelector";
import BrandHeader from "./components/BrandHeader";
import RoutePlanner from "./components/RoutePlanner";

export default function App() {
  const [techId, setTechId] = useState(null);
  const [techName, setTechName] = useState("");
  const [theme, setTheme] = useState("dark");
  const getLocalISODate = () => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  };
  const [selectedDate, setSelectedDate] = useState(() => getLocalISODate());

  const isDark = theme === "dark";
  const pageStyle = {
    minHeight: "100vh",
    background: isDark ? "linear-gradient(135deg, #0f172a 0%, #111827 50%, #0b1220 100%)" : "#f8fafc",
    color: isDark ? "#e2e8f0" : "#0f172a",
    padding: "32px 24px",
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
  };

  const shellStyle = {
    maxWidth: 1200,
    margin: "0 auto",
    background: isDark ? "rgba(15, 23, 42, 0.65)" : "#ffffff",
    border: isDark ? "1px solid rgba(148, 163, 184, 0.25)" : "1px solid #e2e8f0",
    boxShadow: "0 30px 80px rgba(0,0,0,0.15)",
    borderRadius: 18,
    padding: 24,
        backdropFilter: "blur(6px)",
      };

  return (
    <div style={pageStyle}>
      <div style={shellStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <BrandHeader techName={techName} date={selectedDate} theme={theme} />
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontSize: 13, color: isDark ? "#94a3b8" : "#475569" }}>Technician</span>
            <TechSelector value={techId} onChange={setTechId} onTechNameChange={setTechName} />
            <button
              onClick={() => setTheme(isDark ? "light" : "dark")}
              style={{
                padding: "6px 10px",
                borderRadius: 8,
                border: "1px solid #475569",
                background: isDark ? "rgba(51,65,85,0.6)" : "#e2e8f0",
                color: isDark ? "#e2e8f0" : "#0f172a",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              {isDark ? "Light" : "Dark"} mode
            </button>
          </div>
        </div>
        <div style={{ marginTop: 18 }}>
          {techId ? (
            <RoutePlanner techId={techId} theme={theme} onDateChange={setSelectedDate} dateValue={selectedDate} />
          ) : (
            <div style={{ color: isDark ? "#cbd5e1" : "#475569", fontSize: 15 }}>Select a technician to load their route.</div>
          )}
        </div>
      </div>
    </div>
  );
}
