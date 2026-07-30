import { useState, useEffect, useRef } from "react";
import { api } from "../api/client";

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: "#64748b",
  INFO: "#38bdf8",
  WARNING: "#facc15",
  ERROR: "#f87171",
  CRITICAL: "#f43f5e",
};

interface LogEntry { time: string; level: string; module: string; msg: string; }

export function LogViewer() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [level, setLevel] = useState("");
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function fetchLogs() {
    setLoading(true);
    try {
      const data = await api.getLogs(level || undefined, 200) as LogEntry[];
      setLogs(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchLogs(); }, [level]);
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(fetchLogs, 3000);
    return () => clearInterval(id);
  }, [autoRefresh, level]);

  return (
    <div>
      <div style={{ display: "flex", gap: 12, marginBottom: 12, alignItems: "center" }}>
        <select value={level} onChange={(e) => setLevel(e.target.value)}
          style={{ background: "#1e293b", border: "1px solid #334155", color: "#e2e8f0",
            borderRadius: 4, padding: "6px 12px" }}>
          <option value="">Todos los niveles</option>
          <option value="DEBUG">DEBUG</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>
        <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
          <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
          <span style={{ color: "#94a3b8" }}>Auto-refresh</span>
        </label>
        <button onClick={fetchLogs} style={{ background: "#334155", color: "#e2e8f0",
          border: "none", borderRadius: 4, padding: "6px 14px", cursor: "pointer" }}>
          Actualizar
        </button>
        <span style={{ fontSize: 12, color: "#64748b" }}>{loading ? "Cargando..." : `${logs.length} entradas`}</span>
      </div>
      <div style={{ background: "#0f172a", borderRadius: 8, padding: 12, height: 480,
        overflowY: "auto", fontFamily: "monospace", fontSize: 12 }}>
        {logs.map((entry, i) => (
          <div key={i} style={{ marginBottom: 2, display: "flex", gap: 8 }}>
            <span style={{ color: "#475569", flexShrink: 0 }}>{entry.time?.slice(11, 23)}</span>
            <span style={{ color: LEVEL_COLORS[entry.level] ?? "#94a3b8", flexShrink: 0, width: 60 }}>
              {entry.level}
            </span>
            <span style={{ color: "#64748b", flexShrink: 0, width: 120, overflow: "hidden" }}>
              {entry.module}
            </span>
            <span style={{ color: "#cbd5e1" }}>{entry.msg}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
