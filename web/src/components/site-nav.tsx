"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Trophy } from "lucide-react";
import { cn } from "@/lib/utils";
import { RefreshButton } from "@/components/refresh-button";
import { ThemeToggle } from "@/components/theme-toggle";

const LINKS = [
  { href: "/", label: "Início" },
  { href: "/predict", label: "Previsão" },
  { href: "/fixtures", label: "Jogos" },
  { href: "/groups", label: "Grupos" },
  { href: "/monitor", label: "Monitor" },
];

export function SiteNav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:gap-6">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-semibold">
          <Trophy className="size-5 text-emerald-500" />
          <span className="hidden sm:inline">Copa Predictor</span>
          <span className="text-muted-foreground">2026</span>
        </Link>
        <nav className="flex min-w-0 items-center gap-1 overflow-x-auto text-sm">
          {LINKS.map((l) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={cn(
                  "rounded-md px-3 py-1.5 transition-colors hover:bg-accent hover:text-accent-foreground",
                  active ? "bg-accent text-accent-foreground" : "text-muted-foreground"
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <ThemeToggle />
          <RefreshButton />
        </div>
      </div>
    </header>
  );
}
