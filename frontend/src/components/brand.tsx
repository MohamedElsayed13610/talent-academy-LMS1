"use client";

import Image from "next/image";
import { cn } from "@/lib/utils";
import { useBranding } from "@/hooks/use-branding";

/**
 * Logo lockup, never an inline <img> (DESIGN.md §11) so swapping in the final logo file later
 * (ARCHITECTURE.md Q2/A18) is a one-file change. The current asset is the prototype's 240px
 * screenshot crop; replace public/talent-logo.png once the original arrives.
 *
 * The name comes from academy_settings via useBranding() (spec §2: "No hardcoded brand ...
 * names inside components"); "Talent Academy" here is only the pre-fetch fallback, and happens to
 * already match the seeded academy row.
 */
export function Brand({ compact = false, className }: { compact?: boolean; className?: string }) {
  const { data: branding } = useBranding();
  const name = branding?.display_name || "Talent Academy";

  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <Image src="/talent-logo.png" width={40} height={40} alt={name} priority className="rounded-full" />
      {!compact && (
        <span className="flex flex-col leading-tight">
          <strong className="text-body-lg font-bold text-text">{name}</strong>
          <span className="text-overline text-text-subtle">American Diploma</span>
        </span>
      )}
    </div>
  );
}
