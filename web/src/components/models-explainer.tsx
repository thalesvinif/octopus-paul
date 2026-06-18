import { BookText, Flame } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export function ModelsExplainer() {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Card className="border-emerald-500/30 bg-emerald-500/5">
        <CardContent className="space-y-1.5 p-4">
          <div className="flex items-center gap-2 font-semibold">
            <BookText className="size-4 text-emerald-500" />
            Modelo A — Histórico
          </div>
          <p className="text-sm text-muted-foreground">
            Usa a “ficha” de cada seleção: ranking de força, como vêm jogando nos
            últimos jogos e o histórico de confrontos. Funciona bem{" "}
            <span className="font-medium text-foreground">desde o 1º jogo</span>,
            porque sempre há histórico.
          </p>
          <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
            = reputação da seleção
          </p>
        </CardContent>
      </Card>
      <Card className="border-sky-500/30 bg-sky-500/5">
        <CardContent className="space-y-1.5 p-4">
          <div className="flex items-center gap-2 font-semibold">
            <Flame className="size-4 text-sky-500" />
            Modelo B — Só esta Copa
          </div>
          <p className="text-sm text-muted-foreground">
            Esquece o passado e olha só o que a seleção fez{" "}
            <span className="font-medium text-foreground">nesta Copa de 2026</span>.
            No começo quase não tem dados (parte do ranking), mas fica mais preciso
            a cada rodada.
          </p>
          <p className="text-xs font-medium text-sky-600 dark:text-sky-400">
            = fase atual no torneio
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
