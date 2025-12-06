import React from "react";

const PRIMARY = "#1d8bff";
const BG = "rgba(15,23,42,0.85)";

export default function BrandHeader({ techName, date, theme = "dark" }) {
  const isDark = theme === "dark";
  const textColor = isDark ? "#e2e8f0" : "#0f172a";
  const subColor = isDark ? "#cbd5e1" : "#1f2937";
  const cardBg = isDark ? BG : "#f8fafc";
  const border = isDark ? "1px solid rgba(148,163,184,0.25)" : "1px solid rgba(15,23,42,0.08)";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "10px 14px",
        borderRadius: 12,
        border,
        background: cardBg,
        boxShadow: isDark ? "0 8px 24px rgba(0,0,0,0.35)" : "0 6px 16px rgba(15,23,42,0.08)",
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 10,
          overflow: "hidden",
          background: isDark ? "rgba(255,255,255,0.06)" : "rgba(15,23,42,0.04)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: isDark ? "1px solid rgba(148,163,184,0.15)" : "1px solid rgba(15,23,42,0.08)",
        }}
      >
        <img src="/logo_sm.png" alt="Appliance Repair Center" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ color: textColor, fontWeight: 700, fontSize: 16, letterSpacing: "0.01em" }}>Appliance Repair Center</div>
        <div style={{ color: subColor, fontSize: 12 }}>
          {techName ? `Tech: ${techName}` : "Tech: —"} • {date || "—"}
        </div>
      </div>
    </div>
  );
}
