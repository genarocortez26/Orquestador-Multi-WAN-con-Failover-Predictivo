import type { WanMetrics } from "../types";

const STATUS_COLOR = {
  up: "#4ade80",
  degraded: "#facc15",
  down: "#f87171",
};

function getStatus(wan: WanMetrics): keyof typeof STATUS_COLOR {
  if (!wan.is_up) return "down";
  if (wan.is_degraded) return "degraded";
  return "up";
}

function Metric({ label, value, unit, warn }: { label: string; value: number; unit: string; warn?: boolean }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: warn ? "#facc15" : "#e2e8f0" }}>
        {value.toFixed(1)}<span style={{ fontSize: 12, color: "#64748b" }}>{unit}</span>
      </div>
      <div style={{ fontSize: 11, color: "#64748b" }}>{label}</div>
    </div>
  );
}

export function WanCard({ wan, risk }: { wan: WanMetrics; risk?: number }) {
  const status = getStatus(wan);
  const color = STATUS_COLOR[status];
  return (
    <div style={{
      background: "#1e293b", borderRadius: 8, padding: 20,
      border: `2px solid ${color}`, flex: 1, minWidth: 240,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 16 }}>{wan.name}</div>
          <div style={{ fontSize: 12, color: "#64748b" }}>{wan.wan_id}</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          <span style={{ fontSize: 12, color, fontWeight: 600 }}>
            {status === "up" ? "● ACTIVO" : status === "degraded" ? "◐ DEGRADADO" : "○ CAIDO"}
          </span>
          <span style={{ fontSize: 12, color: "#94a3b8" }}>Score: {wan.score.toFixed(0)}</span>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
        <Metric label="Latencia" value={wan.latency_ms} unit="ms" warn={wan.latency_ms > 100} />
        <Metric label="Jitter" value={wan.jitter_ms} unit="ms" warn={wan.jitter_ms > 20} />
        <Metric label="Perdida" value={wan.loss_pct} unit="%" warn={wan.loss_pct > 2} />
      </div>
      {risk !== undefined && risk > 0.5 && (
        <div style={{ marginTop: 12, padding: "6px 10px", background: "#422006",
          borderRadius: 4, fontSize: 12, color: "#fb923c" }}>
          ⚠ Prediccion ML: riesgo de degradacion ({(risk * 100).toFixed(0)}%)
        </div>
      )}
    </div>
  );
}
