"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Branding } from "@/lib/types";

// spec §2: "Branding (name, logo, colors) lives in academy_settings and is applied via CSS
// variables. No hardcoded brand colors or names inside components." Components read this hook
// instead of a literal string/color; globals.css's defaults are only the pre-fetch fallback.
export function useBranding() {
  return useQuery<Branding>({
    queryKey: ["public", "branding"],
    queryFn: () => api.get<Branding>("/public/branding"),
    staleTime: 5 * 60_000,
  });
}
