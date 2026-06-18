import { api } from "@/lib/api";
import { FixturesBrowser } from "@/components/fixtures-browser";
import { ApiError } from "@/components/api-error";

export const dynamic = "force-dynamic";

export default async function FixturesPage() {
  try {
    const fixtures = await api.fixtures();
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Jogos da Copa 2026</h1>
          <p className="text-muted-foreground">
            {fixtures.length} partidas. Filtre por status e grupo.
          </p>
        </div>
        <FixturesBrowser fixtures={fixtures} />
      </div>
    );
  } catch (e) {
    return <ApiError error={e} />;
  }
}
