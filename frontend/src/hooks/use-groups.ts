"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "@/lib/api";
import type { AdminGroup, Page, StudentRow } from "@/lib/types";

export function useGroups(q?: string) {
  return useQuery<Page<AdminGroup>>({
    queryKey: ["admin", "groups", q],
    queryFn: () => api.get<Page<AdminGroup>>(`/admin/groups${q ? `?q=${encodeURIComponent(q)}` : ""}`),
    placeholderData: (prev) => prev,
  });
}

export function useGroup(id: number | null) {
  return useQuery<AdminGroup>({
    queryKey: ["admin", "groups", id],
    queryFn: () => api.get<AdminGroup>(`/admin/groups/${id}`),
    enabled: id !== null,
  });
}

export function useGroupMembers(id: number | null, q?: string) {
  return useQuery<Page<StudentRow>>({
    queryKey: ["admin", "groups", id, "members", q],
    queryFn: () => api.get<Page<StudentRow>>(`/admin/groups/${id}/members${q ? `?q=${encodeURIComponent(q)}` : ""}`),
    enabled: id !== null,
  });
}

function invalidateGroups(queryClient: ReturnType<typeof useQueryClient>, id?: number) {
  queryClient.invalidateQueries({ queryKey: ["admin", "groups"] });
  if (id) queryClient.invalidateQueries({ queryKey: ["admin", "groups", id] });
}

export function useCreateGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; description?: string }) => api.post<AdminGroup>("/admin/groups", payload),
    onSuccess: () => invalidateGroups(queryClient),
    // Rendered inline in the create-group dialog — skip the global toast (app/providers.tsx).
    meta: { silent: true },
  });
}

export function useUpdateGroup(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { name: string; description?: string }) => api.patch<AdminGroup>(`/admin/groups/${id}`, payload),
    onSuccess: () => invalidateGroups(queryClient, id),
  });
}

/** Surfaces the 409 GROUP_IN_USE payload (live_sessions/exams lists) to the caller for display. */
export function useDeleteGroup() {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, number>({
    mutationFn: (id: number) => api.delete(`/admin/groups/${id}`),
    onSuccess: () => invalidateGroups(queryClient),
  });
}

export function useAddMembers(groupId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (studentIds: number[]) => api.post<{ added: number }>(`/admin/groups/${groupId}/members`, { student_ids: studentIds }),
    onSuccess: () => invalidateGroups(queryClient, groupId),
  });
}

export function useRemoveMember(groupId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (studentId: number) => api.delete(`/admin/groups/${groupId}/members/${studentId}`),
    onSuccess: () => invalidateGroups(queryClient, groupId),
  });
}

export function useAddByGrade(groupId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ gradeLevel, dryRun }: { gradeLevel: string; dryRun: boolean }) =>
      api.post<{ would_add: number | null; added: number | null }>(`/admin/groups/${groupId}/members/by-grade`, { grade_level: gradeLevel, dry_run: dryRun }),
    onSuccess: (_data, variables) => {
      if (!variables.dryRun) invalidateGroups(queryClient, groupId);
    },
  });
}

export function useAssignCourse(groupId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ courseId, expiresAt }: { courseId: number; expiresAt?: string | null }) =>
      api.put<AdminGroup>(`/admin/groups/${groupId}/courses/${courseId}`, { expires_at: expiresAt || null }),
    onSuccess: () => invalidateGroups(queryClient, groupId),
  });
}

export function useRemoveCourse(groupId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (courseId: number) => api.delete<AdminGroup>(`/admin/groups/${groupId}/courses/${courseId}`),
    onSuccess: () => invalidateGroups(queryClient, groupId),
  });
}
