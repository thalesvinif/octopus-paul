export const pct = (v: number, digits = 1) => `${(v * 100).toFixed(digits)}%`;

export function matchDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
  });
}

export function matchDateTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Outcome accent colors shared across W/D/L visuals.
export const OUTCOME = {
  home: "var(--chart-2)",
  draw: "var(--muted-foreground)",
  away: "var(--chart-1)",
} as const;
