"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export function RefreshButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      const r = await api.refresh();
      const n = r.result?.finished ?? 0;
      toast.success(`Resultados atualizados — ${n} jogos encerrados.`);
      router.refresh(); // revalida os Server Components (jogos, grupos, etc.)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao atualizar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={run}
      disabled={loading}
      aria-label="Atualizar resultados"
    >
      <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
      <span className="hidden sm:inline">Atualizar</span>
    </Button>
  );
}
