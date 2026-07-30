import type { Flow } from "../types";

const CLASS_COLORS: Record<string, string> = {
  voip: "#a78bfa",
  web: "#38bdf8",
  bulk: "#fb923c",
  other: "#94a3b8",
};

const WAN_COLORS: Record<string, string> = {
  wan1: "#4ade80",
  wan2: "#60a5fa",
};

export function FlowTable({ flows }: { flows: Flow[] }) {
  if (!flows.length) {
    return (
      <div style={{ background: "#1e293b", borderRadius: 8, padding: 24, textAlign: "center", color: "#64748b" }}>
        No hay flujos activos
      </div>
    );
  }
  return (
    <div style={{ background: "#1e293b", borderRadius: 8, overflow: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #334155" }}>
            {["Origen", "Destino", "Proto", "Clase", "WAN", "Duracion"].map((h) => (
              <th key={h} style={{ padding: "10px 14px", textAlign: "left", color: "#64748b", fontWeight: 600 }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {flows.map((f) => (
            <tr key={f.key} style={{ borderBottom: "1px solid #1e3347" }}>
              <td style={{ padding: "8px 14px", color: "#cbd5e1" }}>{f.src_ip}:{f.src_port}</td>
              <td style={{ padding: "8px 14px", color: "#cbd5e1" }}>{f.dst_ip}:{f.dst_port}</td>
              <td style={{ padding: "8px 14px", color: "#94a3b8", textTransform: "uppercase" }}>{f.protocol}</td>
              <td style={{ padding: "8px 14px" }}>
                <span style={{ color: CLASS_COLORS[f.traffic_class] ?? "#94a3b8",
                  background: "#0f172a", padding: "2px 8px", borderRadius: 4, fontSize: 11 }}>
                  {f.traffic_class}
                </span>
              </td>
              <td style={{ padding: "8px 14px" }}>
                <span style={{ color: WAN_COLORS[f.wan_id] ?? "#94a3b8", fontWeight: 600 }}>
                  {f.wan_id}
                </span>
              </td>
              <td style={{ padding: "8px 14px", color: "#64748b" }}>{f.duration_s.toFixed(0)}s</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
