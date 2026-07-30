import { useState } from "react";
import type { Policy } from "../types";
import { api } from "../api/client";

function WeightInput({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 12, color: "#94a3b8" }}>{label}</span>
      <input
        type="number" step="0.05" min="0" max="1" value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        style={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0",
          borderRadius: 4, padding: "4px 8px", width: 80 }}
      />
    </label>
  );
}

export function PolicyEditor({ policy, onSaved }: { policy: Policy; onSaved: () => void }) {
  const [weights, setWeights] = useState({ ...policy.weights });
  const [preferredWan, setPreferredWan] = useState(policy.preferred_wan ?? "");
  const [migrateOnDeg, setMigrateOnDeg] = useState(policy.migrate_on_degradation);
  const [saving, setSaving] = useState(false);

  const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
  const isValid = Math.abs(totalWeight - 1.0) < 0.05;

  async function save() {
    setSaving(true);
    try {
      await api.updatePolicy(policy.traffic_class, {
        weights,
        preferred_wan: preferredWan || null,
        migrate_on_degradation: migrateOnDeg,
      });
      onSaved();
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  const wKey = (k: keyof typeof weights) => (v: number) => setWeights((w) => ({ ...w, [k]: v }));
  return (
    <div style={{ background: "#1e293b", borderRadius: 8, padding: 20 }}>
      <div style={{ fontWeight: 700, marginBottom: 16 }}>
        {policy.traffic_class.toUpperCase()} — {policy.description}
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 16 }}>
        <WeightInput label="Latencia" value={weights.latency} onChange={wKey("latency")} />
        <WeightInput label="Jitter" value={weights.jitter} onChange={wKey("jitter")} />
        <WeightInput label="Perdida" value={weights.loss} onChange={wKey("loss")} />
        <WeightInput label="Costo" value={weights.cost} onChange={wKey("cost")} />
      </div>
      <div style={{ fontSize: 12, color: isValid ? "#4ade80" : "#f87171", marginBottom: 12 }}>
        Suma de pesos: {totalWeight.toFixed(2)} {isValid ? "✓" : "(debe sumar 1.0)"}
      </div>
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 16 }}>
        <label style={{ fontSize: 13, display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ color: "#94a3b8" }}>WAN preferido:</span>
          <select
            value={preferredWan}
            onChange={(e) => setPreferredWan(e.target.value)}
            style={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0",
              borderRadius: 4, padding: "4px 8px" }}
          >
            <option value="">Ninguno (automatico)</option>
            <option value="wan1">WAN 1</option>
            <option value="wan2">WAN 2</option>
          </select>
        </label>
        <label style={{ fontSize: 13, display: "flex", gap: 8, alignItems: "center" }}>
          <input type="checkbox" checked={migrateOnDeg}
            onChange={(e) => setMigrateOnDeg(e.target.checked)} />
          <span style={{ color: "#94a3b8" }}>Migrar ante degradacion</span>
        </label>
      </div>
      <button
        onClick={save} disabled={!isValid || saving}
        style={{ background: isValid ? "#2563eb" : "#334155", color: "#e2e8f0",
          border: "none", borderRadius: 6, padding: "8px 20px", cursor: "pointer" }}
      >
        {saving ? "Guardando..." : "Guardar"}
      </button>
    </div>
  );
}
