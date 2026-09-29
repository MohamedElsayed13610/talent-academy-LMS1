"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DashboardOut } from "@/lib/types";

export function useDashboard() {
  return useQuery<DashboardOut>({
    queryKey: ["me", "dashboard"],
    queryFn: () => api.get<DashboardOut>("/me/dashboard"),
  });
}
