"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

export function Switch({ className, ...props }: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      className={cn(
        "inline-flex h-7 w-12 shrink-0 items-center rounded-full bg-[var(--border-strong)] transition-colors duration-[var(--t-fast)] data-[state=checked]:bg-primary",
        "focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-2",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="block size-5 translate-x-1 rounded-full bg-white shadow transition-transform duration-[var(--t-fast)] data-[state=checked]:translate-x-6 rtl:data-[state=checked]:-translate-x-6 rtl:translate-x-[-4px]" />
    </SwitchPrimitive.Root>
  );
}
