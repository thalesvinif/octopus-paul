import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ProbabilityBar } from "@/components/probability-bar";
import { ScoreMatrixHeatmap } from "@/components/score-matrix-heatmap";
import { TeamFlag } from "@/components/team-flag";
import { pct } from "@/lib/format";
import type { Prediction } from "@/lib/api";

const MODEL_LABEL: Record<Prediction["model"], string> = {
  tournament: "Modelo B · Copa 2026",
  historical: "Modelo A · Histórico",
};

export function PredictionPanel({ p }: { p: Prediction }) {
  const [mlh, mla, mlp] = p.most_likely;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">{MODEL_LABEL[p.model]}</CardTitle>
        <Badge variant={p.model === "tournament" ? "default" : "secondary"}>
          {p.model === "tournament" ? "rápido" : "histórico"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Expected goals scoreline */}
        <div className="flex items-center justify-center gap-4">
          <Side team={p.home} xg={p.expected_home} />
          <div className="text-center">
            <div className="text-3xl font-bold tabular-nums">
              {mlh} <span className="text-muted-foreground">×</span> {mla}
            </div>
            <div className="text-xs text-muted-foreground">
              placar mais provável · {pct(mlp)}
            </div>
          </div>
          <Side team={p.away} xg={p.expected_away} align="right" />
        </div>

        <Separator />

        <ProbabilityBar p={p} />

        <Separator />

        <ScoreMatrixHeatmap p={p} />

        {p.features && p.features.length > 0 ? (
          <>
            <Separator />
            <FeatureTable p={p} />
          </>
        ) : null}

        {p.notes ? (
          <p className="text-xs text-muted-foreground">{p.notes}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function FeatureTable({ p }: { p: Prediction }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">
        Dados usados nesta previsão
      </p>
      <div className="overflow-hidden rounded-md border text-xs">
        <div className="grid grid-cols-[1fr_auto_auto] gap-x-3 bg-muted/50 px-3 py-1.5 font-medium text-muted-foreground">
          <span>Fator</span>
          <span className="text-right tabular-nums">{p.home.code ?? p.home.name}</span>
          <span className="text-right tabular-nums">{p.away.code ?? p.away.name}</span>
        </div>
        {p.features!.map((f, i) => (
          <div
            key={f.label}
            className={`grid grid-cols-[1fr_auto_auto] gap-x-3 px-3 py-1.5 ${
              i % 2 ? "bg-muted/20" : ""
            }`}
          >
            <span className="text-muted-foreground">{f.label}</span>
            <span className="text-right font-medium tabular-nums">
              {f.home ?? "—"}
            </span>
            <span className="text-right font-medium tabular-nums">
              {f.away ?? ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Side({
  team,
  xg,
  align = "left",
}: {
  team: Prediction["home"];
  xg: number;
  align?: "left" | "right";
}) {
  return (
    <div
      className={`flex flex-1 flex-col gap-1 ${
        align === "right" ? "items-end text-right" : "items-start"
      }`}
    >
      <div className="flex items-center gap-2">
        <TeamFlag team={team} className="size-7" />
        <span className="font-medium">{team.name}</span>
      </div>
      <div className="text-xs text-muted-foreground">
        <span className="font-medium text-foreground tabular-nums">
          {xg.toFixed(2)}
        </span>{" "}
        gols esperados
      </div>
    </div>
  );
}
