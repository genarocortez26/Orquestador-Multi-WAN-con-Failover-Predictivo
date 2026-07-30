import type { WanEvent } from "../types";
import { format } from "date-fns";

const EVENT_ICONS: Record<string, string> = {
  failover: "⚡",
  down: "🔴",
  up: "🟢",
  degraded: "🟡",
  prediction_alert: "⚠️",
};

const EVENT_COLORS: Record<string, string> = {
  failover: "#fb923c",
  down: "#f87171",
  up: "#4ade80",
  degraded: "#facc15",
  prediction_alert: "#c084fc",
};

function parseDetails(details?: string): string {
  if (!details) return "";
  try {
    const d = JSON.parse(details);
    if (d.to_wan) return `→ ${d.to_wan} (${d.flows_migrated ?? 0} flujos, ${d.duration_ms?.toFixed(0) ?? 0}ms)`;
    return JSON.stringify(d);
  } catch {
    return details;
  }
}

export function EventTimeline({ events }: { events: WanEvent[] }) {
  if (!events.length) {
    return (
      <div style={{ color: "#64748b", textAlign: "center", padding: 24 }}>
        No hay eventos
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {events.map((evt) => (
        <div key={evt.id} style={{
          display: "flex", gap: 12, alignItems: "flex-start",
          background: "#1e293b", padding: "10px 14px", borderRadius: 6,
          borderLeft: `3px solid ${EVENT_COLORS[evt.event_type] ?? "#475569"}`,
        }}>
          <span style={{ fontSize: 16 }}>{EVENT_ICONS[evt.event_type] ?? "●"}</span>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontWeight: 600, color: EVENT_COLORS[evt.event_type] ?? "#94a3b8" }}>
                {evt.event_type.toUpperCase()} — {evt.wan_id}
              </span>
              <span style={{ fontSize: 11, color: "#64748b" }}>
                {format(new Date(evt.timestamp), "dd/MM HH:mm:ss")}
              </span>
            </div>
            {evt.details && (
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>
                {parseDetails(evt.details)}
              </div>
            )}
            {evt.latency_ms != null && (
              <div style={{ fontSize: 11, color: "#64748b" }}>
                Latencia: {evt.latency_ms.toFixed(1)}ms
                {evt.loss_pct != null && ` | Perdida: ${evt.loss_pct.toFixed(1)}%`}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
