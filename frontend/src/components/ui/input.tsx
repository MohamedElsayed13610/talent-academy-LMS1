import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-11 w-full rounded-md border border-border bg-surface px-3.5 text-body-sm text-text placeholder:text-text-subtle",
        "transition-colors duration-[var(--t-fast)] focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-2 focus-visible:border-border-strong",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export const Label = React.forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label ref={ref} className={cn("text-label text-text", className)} {...props} />
  ),
);
Label.displayName = "Label";
