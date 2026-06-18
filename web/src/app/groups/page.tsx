import { api } from "@/lib/api";
import { GroupTable } from "@/components/group-table";
import { ApiError } from "@/components/api-error";

export const dynamic = "force-dynamic";

export default async function GroupsPage() {
  let standings;
  try {
    standings = await api.standings();
  } catch (e) {
    return <ApiError error={e} />;
  }

  const groups = Object.entries(standings);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Classificação dos grupos</h1>
        <p className="text-muted-foreground">
          Calculada a partir dos jogos já encerrados. Os três primeiros avançam.
        </p>
      </div>
      {groups.length ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {groups.map(([group, rows]) => (
            <GroupTable key={group} group={group} rows={rows} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Ainda não há jogos encerrados para montar a classificação.
        </p>
      )}
    </div>
  );
}
