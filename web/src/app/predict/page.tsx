import { api } from "@/lib/api";
import { MatchPredictor } from "@/components/match-predictor";
import { ModelsExplainer } from "@/components/models-explainer";
import { ApiError } from "@/components/api-error";

export const dynamic = "force-dynamic";

export default async function PredictPage() {
  try {
    const teams = await api.teams();
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Previsão de jogo</h1>
          <p className="text-muted-foreground">
            Escolha duas seleções e compare as duas leituras: histórico e só esta Copa.
          </p>
        </div>
        <ModelsExplainer />
        <MatchPredictor teams={teams} />
      </div>
    );
  } catch (e) {
    return <ApiError error={e} />;
  }
}
