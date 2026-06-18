import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TeamFlag } from "@/components/team-flag";
import { cn } from "@/lib/utils";
import type { StandingRow } from "@/lib/api";

export function GroupTable({
  group,
  rows,
}: {
  group: string;
  rows: StandingRow[];
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Grupo {group}</CardTitle>
      </CardHeader>
      <CardContent className="px-2">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-6">#</TableHead>
              <TableHead>Seleção</TableHead>
              <TableHead className="text-center">J</TableHead>
              <TableHead className="text-center">SG</TableHead>
              <TableHead className="text-center font-semibold">Pts</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r, i) => (
              <TableRow key={r.team.id}>
                <TableCell
                  className={cn(
                    "tabular-nums text-muted-foreground",
                    i < 2 && "font-semibold text-emerald-500"
                  )}
                >
                  {i + 1}
                </TableCell>
                <TableCell>
                  <Link
                    href={`/teams/${r.team.id}`}
                    className="flex items-center gap-2 hover:underline"
                  >
                    <TeamFlag team={r.team} className="size-5" />
                    <span className="truncate">{r.team.name}</span>
                  </Link>
                </TableCell>
                <TableCell className="text-center tabular-nums">{r.played}</TableCell>
                <TableCell className="text-center tabular-nums">
                  {r.gd > 0 ? `+${r.gd}` : r.gd}
                </TableCell>
                <TableCell className="text-center font-semibold tabular-nums">
                  {r.points}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
