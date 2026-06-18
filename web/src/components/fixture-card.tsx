import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TeamFlag } from "@/components/team-flag";
import { matchDateTime } from "@/lib/format";
import type { Fixture } from "@/lib/api";

export function FixtureCard({ fixture }: { fixture: Fixture }) {
  const finished = fixture.status === "FT";
  return (
    <Card className="transition-colors hover:border-emerald-500/40">
      <CardContent className="space-y-3 p-4">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {fixture.group ? `Grupo ${fixture.group}` : fixture.round}
            {fixture.matchday ? ` · Rodada ${fixture.matchday}` : ""}
          </span>
          <Badge variant={finished ? "secondary" : "outline"}>
            {finished ? "Encerrado" : matchDateTime(fixture.date_utc)}
          </Badge>
        </div>

        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
          <TeamLine team={fixture.home} />
          <div className="text-center text-lg font-bold tabular-nums">
            {finished ? (
              <>
                {fixture.home_goals}
                <span className="text-muted-foreground"> × </span>
                {fixture.away_goals}
              </>
            ) : (
              <span className="text-sm text-muted-foreground">×</span>
            )}
          </div>
          <TeamLine team={fixture.away} align="right" />
        </div>

        {!finished && (
          <Button
            render={<Link href={`/fixtures/${fixture.id}`} />}
            nativeButton={false}
            variant="ghost"
            size="sm"
            className="w-full"
          >
            Prever resultado →
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function TeamLine({
  team,
  align = "left",
}: {
  team: Fixture["home"];
  align?: "left" | "right";
}) {
  return (
    <Link
      href={`/teams/${team.id}`}
      className={`flex items-center gap-2 text-sm hover:underline ${
        align === "right" ? "flex-row-reverse text-right" : ""
      }`}
    >
      <TeamFlag team={team} className="size-5" />
      <span className="truncate font-medium">{team.name}</span>
    </Link>
  );
}
