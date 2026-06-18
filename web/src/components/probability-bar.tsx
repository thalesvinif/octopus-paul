import { pct } from "@/lib/format";
import type { Prediction } from "@/lib/api";

export function ProbabilityBar({ p }: { p: Prediction }) {
  const segments = [
    { key: "home", label: p.home.code ?? p.home.name, value: p.p_home_win, cls: "bg-emerald-500" },
    { key: "draw", label: "Empate", value: p.p_draw, cls: "bg-zinc-500" },
    { key: "away", label: p.away.code ?? p.away.name, value: p.p_away_win, cls: "bg-sky-500" },
  ];
  return (
    <div className="space-y-2">
      <div className="flex h-9 w-full overflow-hidden rounded-md text-xs font-medium">
        {segments.map((s) => (
          <div
            key={s.key}
            className={`flex items-center justify-center text-white transition-all ${s.cls}`}
            style={{ width: `${Math.max(s.value * 100, 0)}%` }}
            title={`${s.label}: ${pct(s.value)}`}
          >
            {s.value > 0.08 ? pct(s.value, 0) : ""}
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        {segments.map((s) => (
          <div key={s.key} className="flex items-center gap-1.5">
            <span className={`size-2 rounded-full ${s.cls}`} />
            <span>{s.label}</span>
            <span className="font-medium text-foreground">{pct(s.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
