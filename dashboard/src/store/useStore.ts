import { create } from "zustand";
import type { WanMetrics, Flow, WanEvent, Policy, MetricSample } from "../types";

interface AppState {
  wans: WanMetrics[];
  flows: Flow[];
  events: WanEvent[];
  policies: Policy[];
  metricHistory: Record<string, MetricSample[]>;
  connected: boolean;
  lastFailover: { from: string; to: string; ts: number } | null;
  predictionAlerts: Record<string, number>;
  setWans: (w: WanMetrics[]) => void;
  updateWan: (metrics: WanMetrics) => void;
  setFlows: (f: Flow[]) => void;
  setEvents: (e: WanEvent[]) => void;
  prependEvent: (e: WanEvent) => void;
  setPolicies: (p: Policy[]) => void;
  setConnected: (v: boolean) => void;
  addMetricSample: (wanId: string, sample: MetricSample) => void;
  setLastFailover: (v: AppState["lastFailover"]) => void;
  setPredictionRisk: (wanId: string, risk: number) => void;
}

export const useStore = create<AppState>((set) => ({
  wans: [],
  flows: [],
  events: [],
  policies: [],
  metricHistory: {},
  connected: false,
  lastFailover: null,
  predictionAlerts: {},

  setWans: (wans) => set({ wans }),
  updateWan: (metrics) =>
    set((s) => ({
      wans: s.wans.map((w) => (w.wan_id === metrics.wan_id ? metrics : w)),
    })),
  setFlows: (flows) => set({ flows }),
  setEvents: (events) => set({ events }),
  prependEvent: (e) =>
    set((s) => ({ events: [e, ...s.events].slice(0, 500) })),
  setPolicies: (policies) => set({ policies }),
  setConnected: (connected) => set({ connected }),
  addMetricSample: (wanId, sample) =>
    set((s) => {
      const hist = s.metricHistory[wanId] ?? [];
      const updated = [...hist, sample].slice(-300);
      return { metricHistory: { ...s.metricHistory, [wanId]: updated } };
    }),
  setLastFailover: (lastFailover) => set({ lastFailover }),
  setPredictionRisk: (wanId, risk) =>
    set((s) => ({
      predictionAlerts: { ...s.predictionAlerts, [wanId]: risk },
    })),
}));
