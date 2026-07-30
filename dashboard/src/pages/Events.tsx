import { useEffect } from "react";
import { useStore } from "../store/useStore";
import { api } from "../api/client";
import { EventTimeline } from "../components/EventTimeline";
import type { WanEvent } from "../types";

export default function Events() {
  const events = useStore((s) => s.events);
  const setEvents = useStore((s) => s.setEvents);
  const wans = useStore((s) => s.wans);

  useEffect(() => {
    api.getEvents(100).then((e) => setEvents(e as WanEvent[]));
  }, []);

  const failoverCount = events.filter((e) => e.event_type === "failover").length;
  const downCount = events.filter((e) => e.event_type === "down").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700 }}>Historial de Eventos</h1>
      <div style={{ display: "flex", gap: 16 }}>
        {[
          { label: "Total Eventos", value: events.length, color: "#38bdf8" },
          { label: "Failovers", value: failoverCount, color: "#fb923c" },
          { label: "Caidas", value: downCount, color: "#f87171" },
        ].map((stat) => (
          <div key={stat.label} style={{ background: "#1e293b", borderRadius: 8, padding: "14px 20px",
            flex: 1, textAlign: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: stat.color }}>{stat.value}</div>
            <div style={{ fontSize: 12, color: "#64748b" }}>{stat.label}</div>
          </div>
        ))}
      </div>
      <EventTimeline events={events} />
    </div>
  );
}
