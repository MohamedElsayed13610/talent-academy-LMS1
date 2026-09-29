"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { LeaderboardOut, MyPointsOut } from "@/lib/types";

export function useMyPoints(page: number = 1, pageSize: number = 25) {
  return useQuery<MyPointsOut>({
    queryKey: ["me", "points", page],
    queryFn: () => api.get<MyPointsOut>(`/me/points?page=${page}&page_size=${pageSize}`),
    placeholderData: (prev) => prev,
  });
}

export function useMyLeaderboard(courseId: number | null, limit: number = 50) {
  return useQuery<LeaderboardOut>({
    queryKey: ["me", "leaderboard", courseId, limit],
    queryFn: () => api.get<LeaderboardOut>(`/me/leaderboard?course_id=${courseId}&limit=${limit}`),
    enabled: courseId !== null,
  });
}
