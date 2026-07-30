const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json();
}

// FIX: la BD del orquestador guarda eventos como {id, ts, type, wan_id, detail}
// pero el frontend espera {id, wan_id, event_type, timestamp, details}.
// Sin esta traduccion, EventTimeline crashea con event_type undefined.
function adaptEvent(e: any): any {
  return {
    id: e.id,
    wan_id: e.wan_id ?? "sistema",
    event_type: e.event_type ?? e.type ?? "info",
    timestamp: e.timestamp ?? new Date((e.ts ?? 0) * 1000).toISOString(),
    details: e.details ?? e.detail,
    latency_ms: e.latency_ms,
    loss_pct: e.loss_pct,
  };
}

export const api = {
  getWans: () => get("/wans"),
  getFlows: () => get("/flows"),
  getEvents: (limit = 50) =>
    get<any[]>(`/events?limit=${limit}`).then((evts) => (evts ?? []).map(adaptEvent)),
  getPolicies: () => get("/policies"),
  getStatus: () => get("/status"),
  getLogs: (level?: string, limit = 100) =>
    get(`/logs?limit=${limit}${level ? `&level=${level}` : ""}`),
  getWanHistory: (wanId: string, samples = 60) =>
    get(`/wans/${wanId}/metrics?samples=${samples}`),
  updatePolicy: (trafficClass: string, data: unknown) =>
    put(`/policies/${trafficClass}`, data),
};