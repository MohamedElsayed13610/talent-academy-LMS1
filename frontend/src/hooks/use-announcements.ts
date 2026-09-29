"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminAnnouncementOut, AnnouncementIn, AnnouncementPatch, Page } from "@/lib/types";

export function useAnnouncements(page: number = 1, pageSize: number = 25) {
  return useQuery<Page<AdminAnnouncementOut>>({
    queryKey: ["admin", "announcements", page],
    queryFn: () => api.get<Page<AdminAnnouncementOut>>(`/admin/announcements?page=${page}&page_size=${pageSize}`),
    placeholderData: (prev) => prev,
  });
}

function invalidate(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["admin", "announcements"] });
}

export function useCreateAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AnnouncementIn) => api.post<AdminAnnouncementOut>("/admin/announcements", payload),
    onSuccess: () => invalidate(queryClient),
    meta: { silent: true },
  });
}

export function useUpdateAnnouncement(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AnnouncementPatch) => api.patch<AdminAnnouncementOut>(`/admin/announcements/${id}`, payload),
    onSuccess: () => invalidate(queryClient),
    meta: { silent: true },
  });
}

export function useDeleteAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/admin/announcements/${id}`),
    onSuccess: () => invalidate(queryClient),
  });
}
