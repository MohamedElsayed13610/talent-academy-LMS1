"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminLiveSession, AttendanceSheet, LiveSessionIn, LiveSessionPatch } from "@/lib/types";

export interface LiveSessionFilters {
  course_id?: number;
  group_id?: number;
  status?: string;
  from?: string;
  to?: string;
}

function toQuery(filters: LiveSessionFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useLiveSessions(filters: LiveSessionFilters = {}) {
  return useQuery<AdminLiveSession[]>({
    queryKey: ["admin", "live-sessions", filters],
    queryFn: () => api.get<AdminLiveSession[]>(`/admin/live-sessions${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

function invalidate(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["admin", "live-sessions"] });
}

export function useCreateLiveSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LiveSessionIn) => api.post<AdminLiveSession>("/admin/live-sessions", payload),
    onSuccess: () => invalidate(queryClient),
    meta: { silent: true }, // rendered inline in the create/edit dialog
  });
}

export function useUpdateLiveSession(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LiveSessionPatch) => api.patch<AdminLiveSession>(`/admin/live-sessions/${id}`, payload),
    onSuccess: () => invalidate(queryClient),
    meta: { silent: true },
  });
}

export function useDeleteLiveSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/admin/live-sessions/${id}`),
    onSuccess: () => invalidate(queryClient),
  });
}

export function useAttendanceSheet(sessionId: number | null) {
  return useQuery<AttendanceSheet>({
    queryKey: ["admin", "live-sessions", sessionId, "attendance"],
    queryFn: () => api.get<AttendanceSheet>(`/admin/live-sessions/${sessionId}/attendance`),
    enabled: sessionId !== null,
  });
}

export function useUpdateAttendance(sessionId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, status, note }: { studentId: number; status: string; note?: string }) =>
      api.put<AttendanceSheet>(`/admin/live-sessions/${sessionId}/attendance/${studentId}`, { status, note }),
    onSuccess: (data) => {
      queryClient.setQueryData(["admin", "live-sessions", sessionId, "attendance"], data);
      invalidate(queryClient);
    },
  });
}

export function useFinalizeAttendance(sessionId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<AttendanceSheet>(`/admin/live-sessions/${sessionId}/attendance/finalize`),
    onSuccess: (data) => {
      queryClient.setQueryData(["admin", "live-sessions", sessionId, "attendance"], data);
      invalidate(queryClient);
    },
  });
}
