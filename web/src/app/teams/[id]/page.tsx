import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FixtureCard } from "@/components/fixture-card";
import { TeamFlag } from "@/components/team-flag";
import { ApiError } from "@/components/api-error";

export const dynamic = "force-dynamic";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}

export default async function TeamPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let detail;
  try {
    detail = await api.team(Number(id));
  } catch (e) {
    return <ApiError error={e} />;
  }

  const { team, elo, form_gf, form_ga, tournament, matches } = detail;

  return (
    <div className="space-y-6">
      <Link
        href="/fixtures"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Voltar
      </Link>

      <div className="flex items-center gap-4">
        <TeamFlag team={team} className="size-14 rounded-md" />
        <div>
          <h1 className="text-2xl font-bold">{team.name}</h1>
          <p className="text-muted-foreground">{team.code ?? team.country}</p>
        </div>
      </div>

      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <Stat label="Elo pré-Copa" value={elo ? Math.round(elo) : "—"} />
        <Stat label="Jogos na Copa" value={tournament.matches_played} />
        <Stat
          label="Gols pró / contra (Copa)"
          value={`${tournament.goals_scored} / ${tournament.goals_conceded}`}
        />
        <Stat
          label="Forma (GP / GC por jogo)"
          value={`${form_gf} / ${form_ga}`}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Jogos na Copa 2026</CardTitle>
        </CardHeader>
        <CardContent>
          {matches.length ? (
            <div className="grid gap-4 sm:grid-cols-2">
              {matches.map((f) => (
                <FixtureCard key={f.id} fixture={f} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Sem jogos cadastrados.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
