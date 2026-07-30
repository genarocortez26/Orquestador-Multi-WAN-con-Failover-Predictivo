import { useStore } from "../store/useStore";
import { WanCard } from "../components/WanCard";
import { FlowTable } from "../components/FlowTable";
import { MetricsChart } from "../components/MetricsChart";

export default function Dashboard() {
  const wans = useStore((s) => s.wans);
  const flows = useStore((s) => s.flows);
  const metricHistory = useStore((s) => s.metricHistory);
  const predictionAlerts = useStore((s) => s.predictionAlerts);
  const lastFailover = useStore((s) => s.lastFailover);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ fontSize: 22, fontWeight: 700 }}>Estado de los Enlaces</h1>
        {lastFailover && (
          <div style={{ background: "#422006", color: "#fb923c", padding: "6px 12px",
            borderRadius: 6, fontSize: 13 }}>
            Failover reciente: {lastFailover.from} → {lastFailover.to}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {wans.map((wan) => (
          <WanCard key={wan.wan_id} wan={wan} risk={predictionAlerts[wan.wan_id]} />
        ))}
        {wans.length === 0 && (
          <div style={{ color: "#64748b", padding: 24 }}>
            Conectando al orquestador...
          </div>
        )}
      </div>

      <div>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: "#94a3b8" }}>
          Metricas en Tiempo Real
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: 16 }}>
          {wans.map((wan) => {
            const hist = metricHistory[wan.wan_id] ?? [];
            return (
              <div key={wan.wan_id}>
                <div style={{ fontSize: 13, color: "#64748b", marginBottom: 6 }}>{wan.name}</div>
                <MetricsChart
                  data={hist}
                  title={`${wan.name} — Latencia y Jitter`}
                  metrics={[
                    { key: "latency_ms", color: "#38bdf8", label: "Latencia", unit: "ms" },
                    { key: "jitter_ms", color: "#a78bfa", label: "Jitter", unit: "ms" },
                  ]}
                />
                <div style={{ marginTop: 12 }}>
                  <MetricsChart
                    data={hist}
                    title={`${wan.name} — Perdida de Paquetes`}
                    metrics={[
                      { key: "loss_pct", color: "#f87171", label: "Perdida", unit: "%" },
                    ]}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: "#94a3b8" }}>
          Flujos Activos ({flows.length})
        </h2>
        <FlowTable flows={flows} />
      </div>
    </div>
  );
}
