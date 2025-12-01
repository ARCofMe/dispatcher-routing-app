import { useState } from "react";
import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";

const badgeStyles = {
  pending: { background: "rgba(147, 197, 253, 0.15)", color: "#bfdbfe", border: "1px solid rgba(147,197,253,0.4)" },
  "in-progress": { background: "rgba(251, 191, 36, 0.18)", color: "#fcd34d", border: "1px solid rgba(252,211,77,0.4)" },
  complete: { background: "rgba(74, 222, 128, 0.18)", color: "#4ade80", border: "1px solid rgba(74,222,128,0.4)" },
};

const statusOrder = ["pending", "in-progress", "complete"];

export default function StopList({ stops, onReorder, onStatusChange, onEditStop }) {
  const [expanded, setExpanded] = useState({});
  const bfAccount = import.meta.env.VITE_BLUEFOLDER_ACCOUNT_NAME;

  const toggle = (key) => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleDragEnd = (result) => {
    if (!result.destination) return;
    const updated = Array.from(stops);
    const [moved] = updated.splice(result.source.index, 1);
    updated.splice(result.destination.index, 0, moved);
    onReorder?.(updated);
  };

  return (
    <div style={{ background: "rgba(15,23,42,0.5)", border: "1px solid #334155", borderRadius: 12, padding: 12 }}>
      <h3 style={{ marginBottom: 8, color: "#cbd5e1" }}>Stops</h3>
      <DragDropContext onDragEnd={handleDragEnd}>
        <Droppable droppableId="stops">
          {(provided) => (
            <ol ref={provided.innerRef} {...provided.droppableProps} style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {stops.map((s, i) => (
                <Draggable key={`${s.id}-${i}`} draggableId={`${s.id}-${i}`} index={i}>
                  {(dragProvided) => (
                    <li
                      ref={dragProvided.innerRef}
                      {...dragProvided.draggableProps}
                      {...dragProvided.dragHandleProps}
                      style={{
                        background: "rgba(30,41,59,0.8)",
                        border: "1px solid #334155",
                        borderRadius: 10,
                        padding: "10px 12px",
                        marginBottom: 10,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        color: "#e2e8f0",
                        ...dragProvided.draggableProps.style,
                      }}
                    >
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <div style={{ fontWeight: 600 }}>{i + 1}. {s.customer_name}</div>
                          <button
                            onClick={() => {
                              const current = s.status || "pending";
                              const next = statusOrder[(statusOrder.indexOf(current) + 1) % statusOrder.length];
                              onStatusChange?.(i, next);
                            }}
                            style={{
                              fontSize: 11,
                              padding: "2px 8px",
                              borderRadius: 999,
                              border: badgeStyles[s.status || "pending"].border,
                              background: badgeStyles[s.status || "pending"].background,
                              color: badgeStyles[s.status || "pending"].color,
                              cursor: "pointer",
                            }}
                          >
                            {s.status || "pending"}
                          </button>
                          <button
                            onClick={() => toggle(`edit-${s.id}-${i}`)}
                            style={{
                              fontSize: 11,
                              padding: "2px 8px",
                              borderRadius: 6,
                              border: "1px solid #475569",
                              background: "rgba(51,65,85,0.5)",
                              color: "#e2e8f0",
                              cursor: "pointer",
                            }}
                          >
                            {expanded[`edit-${s.id}-${i}`] ? "Close" : "Edit"}
                          </button>
                        </div>
                        <div style={{ color: "#cbd5e1" }}>{s.address}</div>
                        <div style={{ color: "#cbd5e1", fontSize: 12 }}>
                          Window: {s.window_start || "—"} - {s.window_end || "—"}
                          {s.eta && s.window_end && s.eta > s.window_end && (
                            <span style={{ marginLeft: 8, color: "#f87171" }}>(ETA past window)</span>
                          )}
                        </div>
                        {(s.service_request_id || s.subject) && (
                          <button
                            onClick={() => toggle(`${s.id}-${i}`)}
                            style={{
                              marginTop: 6,
                              padding: "4px 8px",
                              borderRadius: 8,
                              border: "1px solid #334155",
                              background: "rgba(51,65,85,0.6)",
                              color: "#93c5fd",
                              cursor: "pointer",
                              fontSize: 12,
                            }}
                          >
                            {expanded[`${s.id}-${i}`] ? "Hide details" : "Show details"}
                          </button>
                        )}
                        {expanded[`${s.id}-${i}`] && (
                          <div style={{ marginTop: 6, padding: 8, borderRadius: 8, border: "1px solid #334155", background: "rgba(15,23,42,0.6)", display: "grid", gap: 4 }}>
                            {s.service_request_id && <div style={{ fontSize: 12, color: "#e2e8f0" }}>Service Request: {s.service_request_id}</div>}
                            {s.subject && <div style={{ fontSize: 12, color: "#e2e8f0" }}>Subject: {s.subject}</div>}
                            {bfAccount && s.service_request_id && (
                              <a
                                href={`https://${bfAccount}.bluefolder.com/serviceRequests/${s.service_request_id}`}
                                target="_blank"
                                rel="noreferrer"
                                style={{ fontSize: 12, color: "#38bdf8" }}
                              >
                                Open in BlueFolder
                              </a>
                            )}
                          </div>
                        )}
                      </div>
                      <div style={{ textAlign: "right", minWidth: 90, color: "#93c5fd" }}>
                        {s.eta && <div>ETA: {s.eta}</div>}
                        {s.duration_minutes !== undefined && <div style={{ color: "#e2e8f0" }}>{s.duration_minutes}m on site</div>}
                      </div>
                    </li>
                  )}
                </Draggable>
              ))}
              {provided.placeholder}
            </ol>
          )}
        </Droppable>
      </DragDropContext>
    </div>
  );
}
                        {expanded[`edit-${s.id}-${i}`] && (
                          <div style={{ marginTop: 6, padding: 8, borderRadius: 8, border: "1px solid #334155", background: "rgba(15,23,42,0.6)", display: "grid", gap: 6 }}>
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
                              <input
                                type="time"
                                defaultValue={s.window_start || ""}
                                onChange={(e) => (s._editWindowStart = e.target.value)}
                                style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
                              />
                              <input
                                type="time"
                                defaultValue={s.window_end || ""}
                                onChange={(e) => (s._editWindowEnd = e.target.value)}
                                style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
                              />
                              <input
                                type="number"
                                defaultValue={s.duration_minutes || 30}
                                onChange={(e) => (s._editDuration = Number(e.target.value) || 0)}
                                style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #334155", background: "#0f172a", color: "#e2e8f0" }}
                              />
                            </div>
                            <div style={{ display: "flex", gap: 8 }}>
                              <button
                                onClick={() => {
                                  onEditStop?.(i, {
                                    window_start: s._editWindowStart || s.window_start,
                                    window_end: s._editWindowEnd || s.window_end,
                                    duration_minutes: s._editDuration || s.duration_minutes,
                                  });
                                  toggle(`edit-${s.id}-${i}`);
                                }}
                                style={{
                                  padding: "6px 10px",
                                  borderRadius: 6,
                                  border: "1px solid #10b981",
                                  background: "#059669",
                                  color: "#e2e8f0",
                                  cursor: "pointer",
                                  fontSize: 12,
                                }}
                              >
                                Save
                              </button>
                              <button
                                onClick={() => toggle(`edit-${s.id}-${i}`)}
                                style={{
                                  padding: "6px 10px",
                                  borderRadius: 6,
                                  border: "1px solid #475569",
                                  background: "rgba(51,65,85,0.5)",
                                  color: "#e2e8f0",
                                  cursor: "pointer",
                                  fontSize: 12,
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
