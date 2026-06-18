import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { MatchPredictor } from "@/components/match-predictor";
import { TeamFlag } from "@/components/team-flag";
import { ApiError } from "@/components/api-error";
import { matchDateTime } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function FixturePredictPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const fixtureId = Number(id);

  let fixture, teams;
  try {
    const all = await api.fixtures();
    fixture = all.find((f) => f.id === fixtureId);
    teams = await api.teams();
  } catch (e) {
    return <ApiError error={e} />;
  }

  if (!fixture) {
    return (
      <p className="text-sm text-muted-foreground">Jogo não encontrado.</p>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        href="/fixtures"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Voltar aos jogos
      </Link>

      <div className="flex flex-col items-center gap-3 text-center">
        <div className="text-xs text-muted-foreground">
          {fixture.group ? `Grupo ${fixture.group}` : fixture.round} ·{" "}
          {matchDateTime(fixture.date_utc)}
        </div>
        <div className="flex items-center gap-4 text-xl font-bold">
          <span className="flex items-center gap-2">
            <TeamFlag team={fixture.home} className="size-7" />
            {fixture.home.name}
          </span>
          <span className="text-muted-foreground">×</span>
          <span className="flex items-center gap-2">
            {fixture.away.name}
            <TeamFlag team={fixture.away} className="size-7" />
          </span>
        </div>
      </div>

      <MatchPredictor
        teams={teams}
        fixtureId={fixture.id}
        initialHome={fixture.home}
        initialAway={fixture.away}
      />
    </div>
  );
}
