import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { API_URL } from "@/lib/api";

export function ApiError({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <Card className="border-destructive/40">
      <CardContent className="flex items-start gap-3 pt-6">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-destructive" />
        <div className="space-y-1 text-sm">
          <p className="font-medium">Não foi possível falar com a API.</p>
          <p className="text-muted-foreground">
            Confira se o backend está rodando em{" "}
            <code className="rounded bg-muted px-1">{API_URL}</code> — inicie com{" "}
            <code className="rounded bg-muted px-1">
              uvicorn src.api:app --port 8010
            </code>
            .
          </p>
          <p className="text-xs text-muted-foreground">{msg}</p>
        </div>
      </CardContent>
    </Card>
  );
}
