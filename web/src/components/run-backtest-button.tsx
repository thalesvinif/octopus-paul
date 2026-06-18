"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Play, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function RunBacktestButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      const d = await api.monitor.run();
      const n = d.latest?.n_games ?? 0;
      toast.success(`Backtest rodado — ${n} jogos avaliados.`);
      router.refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao rodar o backtest.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button onClick={run} disabled={loading} size="sm">
      {loading ? (
        <Loader2 className="size-4 animate-spin" />
      ) : (
        <Play className="size-4" />
      )}
      Rodar agora
    </Button>
  );
}
