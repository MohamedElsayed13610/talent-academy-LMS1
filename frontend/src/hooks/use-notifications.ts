"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Page, StudentNotificationOut } from "@/lib/types";

export function useMyNotifications(page: number = 1, pageSize: number = 25) {
  return useQuery<Page<StudentNotificationOut>>({
    queryKey: ["me", "notifications", page],
    queryFn: () => api.get<Page<StudentNotificationOut>>(`/me/notifications?page=${page}&page_size=${pageSize}`),
    placeholderData: (prev) => prev,
  });
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post<void>(`/me/notifications/${id}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me", "notifications"] });
      queryClient.invalidateQueries({ queryKey: ["me", "dashboard"] });
    },
    meta: { silent: true },
  });
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/me/notifications/read-all"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me", "notifications"] });
      queryClient.invalidateQueries({ queryKey: ["me", "dashboard"] });
    },
  });
}
