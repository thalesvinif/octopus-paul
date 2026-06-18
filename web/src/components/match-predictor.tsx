"use client";

import { useState } from "react";
import { ArrowLeftRight, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";
import { TeamCombobox } from "@/components/team-combobox";
import { PredictionPanel } from "@/components/prediction-panel";
import { api, type PredictResponse, type Team } from "@/lib/api";

export function MatchPredictor({
  teams,
  initialHome,
  initialAway,
  fixtureId,
}: {
  teams: Team[];
  initialHome?: Team | null;
  initialAway?: Team | null;
  fixtureId?: number;
}) {
  const [home, setHome] = useState<Team | null>(initialHome ?? null);
  const [away, setAway] = useState<Team | null>(initialAway ?? null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictResponse | null>(null);

  async function run() {
    if (!fixtureId && (!home || !away)) {
      toast.error("Escolha as duas seleções.");
      return;
    }
    if (home && away && home.id === away.id) {
      toast.error("Escolha seleções diferentes.");
      return;
    }
    setLoading(true);
    try {
      // Always request both models: Modelo A (histórico) + Modelo B (só Copa).
      const res = await api.predict(
        fixtureId
          ? { fixtureId, historical: true }
          : { home: home!.name, away: away!.name, historical: true }
      );
      setResult(res);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha na previsão.");
    } finally {
      setLoading(false);
    }
  }

  function swap() {
    setHome(away);
    setAway(home);
  }

  const predictButton = (
    <Button onClick={run} disabled={loading}>
      {loading ? (
        <Loader2 className="size-4 animate-spin" />
      ) : (
        <Sparkles className="size-4" />
      )}
      {fixtureId ? "Prever jogo" : "Prever"}
    </Button>
  );

  return (
    <div className="space-y-6">
      {!fixtureId && (
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="grid items-end gap-3 sm:grid-cols-[1fr_auto_1fr]">
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Seleção 1</Label>
                <TeamCombobox teams={teams} value={home} onChange={setHome} />
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={swap}
                className="mb-0.5 hidden sm:inline-flex"
                aria-label="Inverter ordem"
              >
                <ArrowLeftRight className="size-4" />
              </Button>
              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Seleção 2</Label>
                <TeamCombobox teams={teams} value={away} onChange={setAway} />
              </div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                Compara o Modelo A (histórico) com o Modelo B (só dados da Copa).
              </p>
              {predictButton}
            </div>
          </CardContent>
        </Card>
      )}

      {fixtureId && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Compara o Modelo A (histórico) com o Modelo B (só dados da Copa).
          </p>
          {predictButton}
        </div>
      )}

      {loading && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-[26rem] w-full" />
          <Skeleton className="h-[26rem] w-full" />
        </div>
      )}

      {!loading && result && (
        <div
          className={
            result.predictions.length > 1
              ? "grid gap-4 lg:grid-cols-2"
              : "mx-auto max-w-2xl"
          }
        >
          {result.predictions.map((p) => (
            <PredictionPanel key={p.model} p={p} />
          ))}
        </div>
      )}
    </div>
  );
}
