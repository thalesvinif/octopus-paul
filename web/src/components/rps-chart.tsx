"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MonitorSnapshot } from "@/lib/api";

export function RpsChart({ history }: { history: MonitorSnapshot[] }) {
  const data = history.map((h) => ({
    date: h.date.slice(5), // MM-DD
    "Modelo A": h.A_rps,
    "Modelo B": h.B_rps,
    Baseline: h.base_rps,
  }));

  if (data.length < 2) {
    return (
      <p className="py-10 text-center text-sm text-muted-foreground">
        Poucos pontos para um gráfico ainda — volte após alguns dias de snapshots.
        (RPS menor = melhor.)
      </p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} domain={["auto", "auto"]} />
        <Tooltip
          contentStyle={{
            background: "var(--popover)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Line type="monotone" dataKey="Modelo A" stroke="#10b981" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="Modelo B" stroke="#0ea5e9" strokeWidth={2} dot={false} />
        <Line
          type="monotone"
          dataKey="Baseline"
          stroke="#a1a1aa"
          strokeWidth={1.5}
          strokeDasharray="4 4"
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
