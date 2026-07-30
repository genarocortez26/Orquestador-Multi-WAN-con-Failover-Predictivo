import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from "recharts";
import type { MetricSample } from "../types";
import { format } from "date-fns";

interface Props {
  data: MetricSample[];
  title: string;
  metrics: Array<{ key: keyof MetricSample; color: string; label: string; unit: string }>;
}

export function MetricsChart({ data, title, metrics }: Props) {
  const formatted = data.map((s) => ({
    ...s,
    time: format(new Date(s.ts * 1000), "HH:mm:ss"),
  }));
  return (
    <div style={{ background: "#1e293b", borderRadius: 8, padding: 16 }}>
      <div style={{ fontWeight: 600, marginBottom: 12, color: "#94a3b8" }}>{title}</div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={formatted} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fill: "#64748b", fontSize: 10 }} width={40} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 6 }}
            labelStyle={{ color: "#94a3b8" }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {metrics.map((m) => (
            <Line
              key={m.key as string}
              type="monotone"
              dataKey={m.key as string}
              stroke={m.color}
              dot={false}
              strokeWidth={2}
              name={`${m.label} (${m.unit})`}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
