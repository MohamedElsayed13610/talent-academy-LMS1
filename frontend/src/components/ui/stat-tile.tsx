import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function StatTile({
  icon: Icon,
  label,
  value,
  hint,
  tone = "primary",
  className,
}: {
  icon: LucideIcon;
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "primary" | "accent";
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-4 rounded-lg border border-border bg-surface p-5 shadow-[var(--shadow-1)]", className)}>
      <span
        className={cn(
          "flex size-11 shrink-0 items-center justify-center rounded-md",
          tone === "accent" ? "bg-accent-soft text-accent-fg" : "bg-primary-soft text-primary-soft-fg",
        )}
      >
        <Icon size={20} strokeWidth={1.75} />
      </span>
      <div className="flex flex-col">
        <span className="text-caption">{label}</span>
        <strong className="text-metric leading-none">{value}</strong>
        {hint ? <span className="text-caption">{hint}</span> : null}
      </div>
    </div>
  );
}
