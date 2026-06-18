import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { pct } from "@/lib/format";
import type { Prediction } from "@/lib/api";

const MAX = 6; // show 0..6 goals per axis (truncate the 7-7 tail)

export function ScoreMatrixHeatmap({ p }: { p: Prediction }) {
  const matrix = p.score_matrix;
  let peak = 0;
  for (let i = 0; i <= MAX; i++)
    for (let j = 0; j <= MAX; j++) peak = Math.max(peak, matrix[i]?.[j] ?? 0);
  const [mlh, mla] = p.most_likely;

  return (
    <div className="space-y-2">
      <div className="text-xs text-muted-foreground">
        Gols {p.home.code ?? "casa"} (linhas) × {p.away.code ?? "visit."} (colunas)
      </div>
      <div className="overflow-x-auto">
        <div
          className="grid gap-0.5"
          style={{ gridTemplateColumns: `1.5rem repeat(${MAX + 1}, minmax(2rem, 1fr))` }}
        >
          <div />
          {Array.from({ length: MAX + 1 }, (_, j) => (
            <div key={`h${j}`} className="text-center text-xs text-muted-foreground">
              {j}
            </div>
          ))}
          {Array.from({ length: MAX + 1 }, (_, i) => (
            <Row
              key={`r${i}`}
              i={i}
              cells={matrix[i] ?? []}
              peak={peak}
              ml={[mlh, mla]}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function Row({
  i,
  cells,
  peak,
  ml,
}: {
  i: number;
  cells: number[];
  peak: number;
  ml: [number, number];
}) {
  return (
    <>
      <div className="flex items-center justify-center text-xs text-muted-foreground">
        {i}
      </div>
      {Array.from({ length: MAX + 1 }, (_, j) => {
        const v = cells[j] ?? 0;
        const intensity = peak > 0 ? v / peak : 0;
        const isMl = i === ml[0] && j === ml[1];
        return (
          <Tooltip key={j}>
            <TooltipTrigger
              render={
                <div
                  className={cn(
                    "flex aspect-square items-center justify-center rounded-sm text-[10px] tabular-nums",
                    isMl && "ring-2 ring-emerald-400 ring-offset-1 ring-offset-background"
                  )}
                  style={{
                    backgroundColor: `color-mix(in oklab, oklch(0.7 0.16 155) ${Math.round(
                      intensity * 100
                    )}%, var(--muted))`,
                    color: intensity > 0.55 ? "white" : "var(--muted-foreground)",
                  }}
                />
              }
            >
              {v >= 0.01 ? Math.round(v * 100) : ""}
            </TooltipTrigger>
            <TooltipContent>
              {i} × {j} — {pct(v)}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </>
  );
}
