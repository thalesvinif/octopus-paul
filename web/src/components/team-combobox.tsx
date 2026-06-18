"use client";

import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { TeamFlag } from "@/components/team-flag";
import { cn } from "@/lib/utils";
import type { Team } from "@/lib/api";

export function TeamCombobox({
  teams,
  value,
  onChange,
  placeholder = "Selecionar seleção…",
}: {
  teams: Team[];
  value: Team | null;
  onChange: (team: Team) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between"
          />
        }
      >
        {value ? (
          <span className="flex items-center gap-2">
            <TeamFlag team={value} className="size-5" />
            {value.name}
          </span>
        ) : (
          <span className="text-muted-foreground">{placeholder}</span>
        )}
        <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
      </PopoverTrigger>
      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] p-0"
        align="start"
      >
        <Command>
          <CommandInput placeholder="Buscar seleção…" />
          <CommandList>
            <CommandEmpty>Nenhuma seleção encontrada.</CommandEmpty>
            <CommandGroup>
              {teams.map((team) => (
                <CommandItem
                  key={team.id}
                  value={team.name}
                  onSelect={() => {
                    onChange(team);
                    setOpen(false);
                  }}
                >
                  <TeamFlag team={team} className="size-5" />
                  <span className="flex-1">{team.name}</span>
                  <Check
                    className={cn(
                      "size-4",
                      value?.id === team.id ? "opacity-100" : "opacity-0"
                    )}
                  />
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
