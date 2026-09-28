"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { JoinResponse, LiveSessionCard } from "@/lib/types";

export function useMyLiveSessions(status?: string) {
  return useQuery<LiveSessionCard[]>({
    queryKey: ["me", "live-sessions", status],
    queryFn: () => api.get<LiveSessionCard[]>(`/me/live-sessions${status ? `?status=${status}` : ""}`),
    refetchInterval: 30_000, // can_join flips as the clock passes join_opens_at/ends_at
  });
}

export function useJoinLiveSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: number) => api.post<JoinResponse>(`/me/live-sessions/${sessionId}/join`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me", "live-sessions"] }),
  });
}
