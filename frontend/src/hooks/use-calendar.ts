"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CalendarEventOut } from "@/lib/types";

export function useMyCalendar(from: string, to: string) {
  return useQuery<CalendarEventOut[]>({
    queryKey: ["me", "calendar", from, to],
    queryFn: () => api.get<CalendarEventOut[]>(`/me/calendar?${new URLSearchParams({ from, to }).toString()}`),
    placeholderData: (prev) => prev,
  });
}
