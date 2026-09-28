import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-body-sm font-medium", {
  variants: {
    tone: {
      neutral: "bg-neutral-soft text-neutral-fg",
      success: "bg-success-soft text-success-fg",
      warning: "bg-warning-soft text-warning-fg",
      danger: "bg-danger-soft text-danger-fg",
      info: "bg-info-soft text-info-fg",
      primary: "bg-primary-soft text-primary-soft-fg",
      accent: "bg-accent-soft text-accent-fg",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone, className }))} {...props} />;
}
