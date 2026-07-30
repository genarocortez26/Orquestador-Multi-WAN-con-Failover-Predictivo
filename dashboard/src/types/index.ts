export interface WanMetrics {
  wan_id: string;
  name: string;
  latency_ms: number;
  jitter_ms: number;
  loss_pct: number;
  bandwidth_mbps: number;
  is_up: boolean;
  is_degraded: boolean;
  score: number;
  prediction_risk: number;
  last_updated: number;
}

export interface Flow {
  key: string;
  src_ip: string;
  src_port: number;
  dst_ip: string;
  dst_port: number;
  protocol: string;
  traffic_class: string;
  wan_id: string;
  duration_s: number;
  bytes_sent: number;
}

export interface WanEvent {
  id: number;
  wan_id: string;
  event_type: string;
  timestamp: string;
  latency_ms?: number;
  loss_pct?: number;
  details?: string;
}

export interface PolicyWeights {
  latency: number;
  jitter: number;
  loss: number;
  cost: number;
}

export interface HardLimits {
  max_loss_pct?: number;
  max_latency_ms?: number;
  max_jitter_ms?: number;
}

export interface Policy {
  name: string;
  description: string;
  traffic_class: string;
  weights: PolicyWeights;
  hard_limits: HardLimits;
  preferred_wan: string | null;
  migrate_on_degradation: boolean;
}

export interface MetricSample {
  ts: number;
  latency_ms: number;
  jitter_ms: number;
  loss_pct: number;
}

export type WsMessage =
  | { type: "snapshot"; data: Record<string, WanMetrics>; flows: Flow[]; timestamp: number }
  | { type: "metrics"; data: WanMetrics }
  | { type: "failover"; data: { from_wan: string; to_wan: string; flows_migrated: number; duration_ms: number } }
  | { type: "prediction_alert"; data: { wan_id: string; risk: number } }
  | { type: "heartbeat"; timestamp: number };

export type TrafficClass = "voip" | "web" | "bulk" | "other";
