import { api, type MonitorData } from "@/lib/api";
import { ApiError } from "@/components/api-error";
import { ModelsExplainer } from "@/components/models-explainer";
import { MonitorDashboard } from "@/components/monitor-dashboard";
import { RunBacktestButton } from "@/components/run-backtest-button";

export const dynamic = "force-dynamic";

export default async function MonitorPage() {
  let data: MonitorData;
  try {
    data = await api.monitor.history();
  } catch (e) {
    return <ApiError error={e} />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Monitoramento dos modelos</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Como os modelos estão se saindo nos jogos já disputados da Copa.
            Um snapshot é gravado por dia; veja a evolução e se vale recalibrar.
          </p>
        </div>
        <RunBacktestButton />
      </div>

      <ModelsExplainer />
      <MonitorDashboard data={data} />
    </div>
  );
}
