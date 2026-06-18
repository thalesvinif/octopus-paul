"use client";

import { useMemo, useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FixtureCard } from "@/components/fixture-card";
import type { Fixture } from "@/lib/api";

const STATUS_TABS = [
  { value: "all", label: "Todos" },
  { value: "NS", label: "Agendados" },
  { value: "FT", label: "Encerrados" },
];

export function FixturesBrowser({ fixtures }: { fixtures: Fixture[] }) {
  const [status, setStatus] = useState("all");
  const [group, setGroup] = useState("all");

  const groups = useMemo(
    () =>
      Array.from(
        new Set(fixtures.map((f) => f.group).filter((g): g is string => !!g))
      ).sort(),
    [fixtures]
  );

  const filtered = fixtures.filter((f) => {
    if (status !== "all" && f.status !== status) return false;
    if (group !== "all" && f.group !== group) return false;
    return true;
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={status} onValueChange={setStatus}>
          <TabsList>
            {STATUS_TABS.map((t) => (
              <TabsTrigger key={t.value} value={t.value}>
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Select value={group} onValueChange={(v) => setGroup(v ?? "all")}>
          <SelectTrigger className="w-44">
            <SelectValue placeholder="Grupo" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos os grupos</SelectItem>
            {groups.map((g) => (
              <SelectItem key={g} value={g}>
                Grupo {g}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {filtered.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((f) => (
            <FixtureCard key={f.id} fixture={f} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Nenhum jogo para esse filtro.
        </p>
      )}
    </div>
  );
}
