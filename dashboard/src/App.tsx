import { useEffect } from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { wsClient } from "./api/websocket";
import { api } from "./api/client";
import { useStore } from "./store/useStore";
import type { WanMetrics } from "./types";
import Dashboard from "./pages/Dashboard";
import Events from "./pages/Events";
import Policies from "./pages/Policies";
import Logs from "./pages/Logs";

// FIX: el orquestador manda {id, status, uptime_pct, latency_ms, ...} pero el
// frontend espera {wan_id, is_up, is_degraded, score, ...}.
function adaptWan(w: any): WanMetrics {
  return {
    wan_id: w.wan_id ?? w.id,
    name: w.name ?? w.id,
    latency_ms: w.latency_ms ?? 0,
    jitter_ms: w.jitter_ms ?? 0,
    loss_pct: w.loss_pct ?? 0,
    bandwidth_mbps:
      w.bandwidth_mbps ?? (w.throughput_bps ? w.throughput_bps / 1_000_000 : 0),
    is_up: w.is_up ?? (w.status !== "down"),
    is_degraded: w.is_degraded ?? (w.status === "degraded"),
    score: w.score ?? (w.uptime_pct ?? 0),
    prediction_risk: w.prediction_risk ?? 0,
    last_updated: w.last_updated ?? Date.now() / 1000,
  };
}

// FIX v2: el backend manda cada flujo como
//   { flow: "tcp:192.168.10.10:5000->172.16.10.100:8000", class: "web", wan_id: "wan1" }
// (el campo "flow" es un STRING con formato proto:src:sport->dst:dport).
// Lo parseamos para llenar la tabla con origen/destino/protocolo reales.
function adaptFlow(f: any): any {
  const raw: string =
    typeof f.flow === "string" ? f.flow : f.flow?.key ?? f.key ?? "";
  let proto = "?", src = "?", sport = 0, dst = "?", dport = 0;
  const m = raw.match(/^(\w+):([\d.]+):(\d+)->([\d.]+):(\d+)$/);
  if (m) {
    proto = m[1];
    src = m[2];
    sport = Number(m[3]);
    dst = m[4];
    dport = Number(m[5]);
  }
  return {
    key: raw || JSON.stringify(f),
    src_ip: f.src_ip ?? src,
    src_port: f.src_port ?? sport,
    dst_ip: f.dst_ip ?? dst,
    dst_port: f.dst_port ?? dport,
    protocol: f.protocol ?? proto,
    traffic_class: f.traffic_class ?? f.class ?? "other",
    wan_id: f.wan_id ?? "?",
    duration_s: f.duration_s ?? 0,
    bytes_sent: f.bytes_sent ?? 0,
  };
}

function Nav() {
  const connected = useStore((s) => s.connected);
  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `nav-link${isActive ? " active" : ""}`;
  return (
    <nav style={{ background: "#1e293b", padding: "12px 24px", display: "flex", alignItems: "center", gap: 24 }}>
      <span style={{ color: "#38bdf8", fontWeight: 700, fontSize: 16, marginRight: 16 }}>
        MultiWAN
      </span>
      <NavLink to="/" className={linkCls} end>Dashboard</NavLink>
      <NavLink to="/events" className={linkCls}>Eventos</NavLink>
      <NavLink to="/policies" className={linkCls}>Politicas</NavLink>
      <NavLink to="/logs" className={linkCls}>Logs</NavLink>
      <span style={{ marginLeft: "auto", fontSize: 12, color: connected ? "#4ade80" : "#f87171" }}>
        {connected ? "● Conectado" : "○ Desconectado"}
      </span>
    </nav>
  );
}

export default function App() {
  const { setWans, setFlows, setEvents, setConnected,
          addMetricSample, setPredictionRisk } = useStore();

  useEffect(() => {
    // Aplica un estado completo (viene del WS o del polling REST)
    const applyState = (rawWans: any[], rawFlows?: any[], prediction?: any) => {
      const wans = (rawWans ?? []).map(adaptWan);
      setWans(wans);
      if (Array.isArray(rawFlows)) setFlows(rawFlows.map(adaptFlow));

      const now = Date.now() / 1000;
      wans.forEach((w: WanMetrics) =>
        addMetricSample(w.wan_id, {
          ts: now,
          latency_ms: w.latency_ms,
          jitter_ms: w.jitter_ms,
          loss_pct: w.loss_pct,
        })
      );

      const alerts = prediction?.alerts ?? {};
      Object.entries(alerts).forEach(([id, v]) =>
        setPredictionRisk(id, v ? 1 : 0)
      );
    };

    // Carga inicial via REST
    api.getWans().then((w: any) => applyState(w)).catch(() => {});
    api.getFlows().then((f: any) => setFlows((f ?? []).map(adaptFlow))).catch(() => {});
    api.getEvents().then((e: any) => setEvents(e ?? [])).catch(() => {});

    wsClient.connect();
    setConnected(false);

    // Camino principal: snapshot por WebSocket cada 1s
    const unsub = wsClient.onMessage((msg: any) => {
      setConnected(true);
      if (Array.isArray(msg.wans)) applyState(msg.wans, msg.flows, msg.prediction);
    });

    // FALLBACK: si el WS no esta conectado, sondear la API cada 2s
    // para que las tarjetas y los graficos sigan actualizandose igual.
    const poll = setInterval(() => {
      if (useStore.getState().connected) return;
      Promise.all([api.getWans(), api.getFlows()])
        .then(([w, f]: any[]) => applyState(w, f))
        .catch(() => {});
    }, 2000);

    return () => {
      unsub();
      wsClient.disconnect();
      clearInterval(poll);
    };
  }, []);

  return (
    <BrowserRouter>
      <style>{`
        a.nav-link { color: #94a3b8; text-decoration: none; font-size: 14px; padding: 4px 8px; border-radius: 4px; }
        a.nav-link:hover { color: #e2e8f0; background: #334155; }
        a.nav-link.active { color: #38bdf8; background: #1e3a5f; }
      `}</style>
      <Nav />
      <main style={{ padding: 24, minHeight: "calc(100vh - 52px)" }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/events" element={<Events />} />
          <Route path="/policies" element={<Policies />} />
          <Route path="/logs" element={<Logs />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}