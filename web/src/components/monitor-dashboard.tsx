import { AlertTriangle, CheckCircle2, Eye } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { RpsChart } from "@/components/rps-chart";
import type { MonitorData } from "@/lib/api";

const pct = (x: number) => `${(x * 100).toFixed(0)}%`;
const f3 = (x: number) => x.toFixed(3);

const BANNER = {
  green: { cls: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300", Icon: CheckCircle2, label: "Recalibração não necessária" },
  yellow: { cls: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300", Icon: Eye, label: "De olho" },
  red: { cls: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300", Icon: AlertTriangle, label: "Reconsiderar calibração" },
} as const;

export function MonitorDashboard({ data }: { data: MonitorData }) {
  const { latest, recalibration: rc, history } = data;
  const b = BANNER[rc.state];

  if (!latest) {
    return (
      <p className="text-sm text-muted-foreground">
        Nenhum snapshot ainda. Clique em “Rodar agora”.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {/* Recalibration trigger banner */}
      <div className={`flex items-start gap-3 rounded-lg border p-4 ${b.cls}`}>
        <b.Icon className="mt-0.5 size-5 shrink-0" />
        <div className="space-y-0.5">
          <div className="font-semibold">{b.label}</div>
          <p className="text-sm opacity-90">{rc.reason}</p>
        </div>
      </div>

      {/* Current metrics */}
      <div className="grid gap-4 sm:grid-cols-2">
        <MetricCard
          title="Modelo A — Histórico"
          color="emerald"
          acc={latest.A_acc}
          rps={latest.A_rps}
          brier={latest.A_brier}
          drawPred={latest.A_draw_pred}
          baseRps={latest.base_rps}
        />
        <MetricCard
          title="Modelo B — Só esta Copa"
          color="sky"
          acc={latest.B_acc}
          rps={latest.B_rps}
          brier={latest.B_brier}
          drawPred={latest.B_draw_pred}
          baseRps={latest.base_rps}
        />
      </div>

      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
        <span>Jogos avaliados: <b className="text-foreground">{latest.n_games}</b></span>
        <span>Empate real: <b className="text-foreground">{pct(latest.draw_rate_real)}</b></span>
        <span>Empate previsto (A): <b className="text-foreground">{pct(latest.A_draw_pred)}</b></span>
        <span>Snapshot: <b className="text-foreground">{latest.date}</b></span>
      </div>

      {/* RPS evolution */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Evolução do RPS (menor = melhor)</CardTitle>
        </CardHeader>
        <CardContent>
          <RpsChart history={history} />
        </CardContent>
      </Card>

      {/* Recent snapshots */}
      {history.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Snapshots recentes</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-xs text-muted-foreground">
                <tr className="text-right [&>th]:px-2 [&>th]:py-1.5 [&>th:first-child]:text-left">
                  <th>Data</th><th>Jogos</th><th>Emp. real</th>
                  <th>RPS A</th><th>RPS B</th><th>Baseline</th>
                </tr>
              </thead>
              <tbody>
                {[...history].reverse().slice(0, 14).map((h) => (
                  <tr key={h.date} className="border-t text-right [&>td]:px-2 [&>td]:py-1.5 [&>td:first-child]:text-left">
                    <td>{h.date}</td>
                    <td>{h.n_games}</td>
                    <td>{pct(h.draw_rate_real)}</td>
                    <td>{f3(h.A_rps)}</td>
                    <td>{f3(h.B_rps)}</td>
                    <td className="text-muted-foreground">{f3(h.base_rps)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function MetricCard({
  title, color, acc, rps, brier, drawPred, baseRps,
}: {
  title: string;
  color: "emerald" | "sky";
  acc: number;
  rps: number;
  brier: number;
  drawPred: number;
  baseRps: number;
}) {
  const beatsBaseline = rps < baseRps;
  return (
    <Card className={color === "emerald" ? "border-emerald-500/30" : "border-sky-500/30"}>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">{title}</CardTitle>
        <Badge variant={beatsBaseline ? "default" : "secondary"}>
          {beatsBaseline ? "acima do baseline" : "abaixo do baseline"}
        </Badge>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-3 text-sm">
        <Stat label="Acerto 1X2" value={pct(acc)} />
        <Stat label="RPS ↓" value={f3(rps)} />
        <Stat label="Brier ↓" value={f3(brier)} />
        <Stat label="Empate previsto" value={pct(drawPred)} />
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}
