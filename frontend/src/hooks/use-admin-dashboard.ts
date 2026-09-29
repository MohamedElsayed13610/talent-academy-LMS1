"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminDashboardOut } from "@/lib/types";

export function useAdminDashboard() {
  return useQuery<AdminDashboardOut>({
    queryKey: ["admin", "dashboard"],
    queryFn: () => api.get<AdminDashboardOut>("/admin/dashboard"),
  });
}
