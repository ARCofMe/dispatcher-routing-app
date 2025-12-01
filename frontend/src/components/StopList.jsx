import { DragDropContext, Droppable, Draggable } from "@hello-pangea/dnd";

export default function StopList({ stops, onReorder }) {
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
                        <div style={{ fontWeight: 600 }}>{i + 1}. {s.customer_name}</div>
                        <div style={{ color: "#cbd5e1" }}>{s.address}</div>
                        {s.window_start && s.window_end && (
                          <div style={{ color: "#cbd5e1", fontSize: 12 }}>Window: {s.window_start} - {s.window_end}</div>
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
