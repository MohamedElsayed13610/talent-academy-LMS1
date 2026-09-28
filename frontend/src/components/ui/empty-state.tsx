import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-14 px-6 text-center", className)}>
      <span className="flex size-14 items-center justify-center rounded-full bg-primary-soft text-primary-soft-fg">
        <Icon size={26} strokeWidth={1.75} />
      </span>
      <h3 className="text-h3">{title}</h3>
      {description ? <p className="max-w-sm text-body-sm text-text-muted">{description}</p> : null}
      {action}
    </div>
  );
}
