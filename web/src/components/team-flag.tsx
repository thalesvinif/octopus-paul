import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import type { Team } from "@/lib/api";

export function TeamFlag({
  team,
  className,
}: {
  team: Pick<Team, "name" | "code" | "flag_url">;
  className?: string;
}) {
  return (
    <Avatar className={cn("size-6 rounded-sm", className)}>
      {team.flag_url ? (
        <AvatarImage src={team.flag_url} alt={team.name} className="object-cover" />
      ) : null}
      <AvatarFallback className="rounded-sm text-[10px] font-semibold">
        {team.code ?? team.name.slice(0, 3).toUpperCase()}
      </AvatarFallback>
    </Avatar>
  );
}
