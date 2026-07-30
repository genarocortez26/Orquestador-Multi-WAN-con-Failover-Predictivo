import { useEffect, useState } from "react";
import { useStore } from "../store/useStore";
import { api } from "../api/client";
import { PolicyEditor } from "../components/PolicyEditor";
import type { Policy } from "../types";

export default function Policies() {
  const policies = useStore((s) => s.policies);
  const setPolicies = useStore((s) => s.setPolicies);
  const [activeClass, setActiveClass] = useState<string | null>(null);

  async function reload() {
    const data = await api.getPolicies() as Policy[];
    setPolicies(data);
  }

  useEffect(() => { reload(); }, []);

  const active = policies.find((p) => p.traffic_class === activeClass);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700 }}>Configuracion de Politicas</h1>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        {policies.map((p) => (
          <button key={p.traffic_class}
            onClick={() => setActiveClass(p.traffic_class)}
            style={{
              background: activeClass === p.traffic_class ? "#2563eb" : "#1e293b",
              color: "#e2e8f0", border: "1px solid #334155", borderRadius: 6,
              padding: "10px 20px", cursor: "pointer", fontSize: 14,
            }}>
            {p.traffic_class.toUpperCase()}
          </button>
        ))}
      </div>
      {active && (
        <PolicyEditor key={active.traffic_class} policy={active} onSaved={reload} />
      )}
      {!active && policies.length > 0 && (
        <div style={{ color: "#64748b" }}>Selecciona una politica para editar</div>
      )}
    </div>
  );
}
