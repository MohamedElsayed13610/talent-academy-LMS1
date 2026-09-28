"use client";

import { useEffect } from "react";
import { useBranding } from "@/hooks/use-branding";

// Applies academy_settings.primary_color/accent_color as CSS variable overrides once fetched
// (DESIGN.md tokens are the pre-fetch fallback, not a hardcoded brand — spec §2). Client-side by
// design: an SSR-time fetch here would couple the frontend's `next build` to the backend being
// reachable at build time, which is fragile (docs/ARCHITECTURE.md §10 keeps the two independently
// deployable). The seeded defaults already match the CSS fallback, so there's no visible flash.
export function BrandingEffect() {
  const { data } = useBranding();

  useEffect(() => {
    if (!data) return;
    const root = document.documentElement.style;
    root.setProperty("--primary", data.primary_color);
    root.setProperty("--primary-soft-fg", data.primary_color);
    root.setProperty("--ring", data.primary_color);
    root.setProperty("--accent", data.accent_color);
    root.setProperty("--accent-fg", data.accent_color);
    if (data.display_name) {
      document.title = data.display_name;
    }
  }, [data]);

  return null;
}
