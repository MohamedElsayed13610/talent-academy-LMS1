import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-label font-medium transition-colors duration-[var(--t-fast)] disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-2",
  {
    variants: {
      variant: {
        primary: "bg-primary text-primary-fg hover:bg-primary-hover",
        secondary: "bg-surface-2 text-text border border-border hover:bg-surface-raised",
        ghost: "hover:bg-surface-2 text-text",
        danger: "bg-danger-fg text-white hover:opacity-90",
        gold: "bg-accent text-[var(--brand-900)] hover:opacity-90",
      },
      size: {
        sm: "h-9 px-3 text-sm",
        md: "h-11 px-4",
        lg: "h-[52px] px-6 text-body-lg",
        icon: "h-11 w-11",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading, disabled, children, ...props }, ref) => {
    // Radix Slot requires exactly one element child, so the loading spinner (an extra sibling)
    // can only be rendered for a real <button> — asChild callers (e.g. Button asChild with a
    // single <Link>) never pass loading anyway.
    if (asChild) {
      return (
        <Slot className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props}>
          {children}
        </Slot>
      );
    }
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {loading ? <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden /> : null}
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";
