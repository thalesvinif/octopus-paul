import Link from "next/link";
import { ArrowRight, CalendarClock, Trophy } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { FixtureCard } from "@/components/fixture-card";
import { GroupTable } from "@/components/group-table";
import { ApiError } from "@/components/api-error";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let fixtures, standings;
  try {
    [fixtures, standings] = await Promise.all([api.fixtures(), api.standings()]);
  } catch (e) {
    return <ApiError error={e} />;
  }

  const upcoming = fixtures.filter((f) => f.status === "NS").slice(0, 6);
  const recent = fixtures
    .filter((f) => f.status === "FT")
    .slice(-3)
    .reverse();
  const featuredGroups = Object.entries(standings).slice(0, 3);

  return (
    <div className="space-y-10">
      {/* Hero */}
      <section className="overflow-hidden rounded-xl border bg-gradient-to-br from-emerald-500/10 via-background to-sky-500/10 p-8">
        <div className="flex items-center gap-2 text-sm text-emerald-500">
          <Trophy className="size-4" /> Copa do Mundo 2026
        </div>
        <h1 className="mt-2 max-w-2xl text-3xl font-bold sm:text-4xl">
          Previsões de jogos com modelo Bayesiano sobre dados reais do torneio.
        </h1>
        <p className="mt-2 max-w-xl text-muted-foreground">
          O Modelo B atualiza a força de cada seleção a cada partida da Copa. Escolha
          um confronto e veja placar esperado, probabilidades e a matriz de resultados.
        </p>
        <div className="mt-5 flex gap-3">
          <Button render={<Link href="/predict" />} nativeButton={false}>
            Fazer previsão <ArrowRight className="size-4" />
          </Button>
          <Button
            render={<Link href="/fixtures" />}
            nativeButton={false}
            variant="outline"
          >
            Ver jogos
          </Button>
        </div>
      </section>

      {/* Upcoming */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-xl font-semibold">
            <CalendarClock className="size-5 text-muted-foreground" /> Próximos jogos
          </h2>
          <Button
            render={<Link href="/fixtures" />}
            nativeButton={false}
            variant="ghost"
            size="sm"
          >
            Todos →
          </Button>
        </div>
        {upcoming.length ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {upcoming.map((f) => (
              <FixtureCard key={f.id} fixture={f} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Sem jogos agendados.</p>
        )}
      </section>

      {/* Recent results */}
      {recent.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-xl font-semibold">Resultados recentes</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((f) => (
              <FixtureCard key={f.id} fixture={f} />
            ))}
          </div>
        </section>
      )}

      {/* Standings snapshot */}
      {featuredGroups.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Classificação</h2>
            <Button
              render={<Link href="/groups" />}
              nativeButton={false}
              variant="ghost"
              size="sm"
            >
              Todos os grupos →
            </Button>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {featuredGroups.map(([group, rows]) => (
              <GroupTable key={group} group={group} rows={rows} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
