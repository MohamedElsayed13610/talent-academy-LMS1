"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  DeletePreview,
  ImportCommitResult,
  ImportPreview,
  Page,
  StudentBulkActionInput,
  StudentCreateInput,
  StudentCreateResponse,
  StudentDetail,
  StudentRow,
  StudentUpdateInput,
} from "@/lib/types";

export interface StudentFilters {
  q?: string;
  grade?: string;
  type?: string;
  subscription?: string;
  group_id?: number;
  course_id?: number;
  active?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
}

function toQuery(filters: StudentFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useStudents(filters: StudentFilters) {
  return useQuery<Page<StudentRow>>({
    queryKey: ["admin", "students", filters],
    queryFn: () => api.get<Page<StudentRow>>(`/admin/students${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useStudent(id: number | null) {
  return useQuery<StudentDetail>({
    queryKey: ["admin", "students", id],
    queryFn: () => api.get<StudentDetail>(`/admin/students/${id}`),
    enabled: id !== null,
  });
}

export function useDeletePreview(id: number | null) {
  return useQuery<DeletePreview>({
    queryKey: ["admin", "students", id, "delete-preview"],
    queryFn: () => api.get<DeletePreview>(`/admin/students/${id}/delete-preview`),
    enabled: id !== null,
  });
}

function invalidateStudents(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["admin", "students"] });
}

export function useCreateStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StudentCreateInput) => api.post<StudentCreateResponse>("/admin/students", payload),
    onSuccess: () => invalidateStudents(queryClient),
    // The create-student form renders this error inline (StudentFormFields' `error` prop) — skip
    // the global toast so it isn't shown twice (see app/providers.tsx MutationCache).
    meta: { silent: true },
  });
}

export function useUpdateStudent(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StudentUpdateInput) => api.patch<StudentDetail>(`/admin/students/${id}`, payload),
    onSuccess: () => invalidateStudents(queryClient),
    meta: { silent: true }, // rendered inline by StudentFormFields, same reasoning as useCreateStudent
  });
}

export function useDeleteStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/admin/students/${id}`),
    onSuccess: () => invalidateStudents(queryClient),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ id, password }: { id: number; password?: string }) =>
      api.post<{ generated_password: string | null }>(`/admin/students/${id}/reset-password`, { password: password || null }),
  });
}

export function useBulkAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StudentBulkActionInput) => api.post<{ affected: number }>("/admin/students/bulk", payload),
    onSuccess: () => invalidateStudents(queryClient),
  });
}

export function useEnrollStudent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, courseId, expiresAt }: { studentId: number; courseId: number; expiresAt?: string | null }) =>
      api.put<StudentDetail>(`/admin/students/${studentId}/enrollments/${courseId}`, { expires_at: expiresAt || null }),
    onSuccess: () => invalidateStudents(queryClient),
  });
}

export function useRemoveEnrollment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ studentId, courseId }: { studentId: number; courseId: number }) =>
      api.delete(`/admin/students/${studentId}/enrollments/${courseId}`),
    onSuccess: () => invalidateStudents(queryClient),
  });
}

export function useImportPreview() {
  return useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.postForm<ImportPreview>("/admin/students/import/preview", form);
    },
    meta: { silent: true }, // rendered inline in the import page, not as a global toast
  });
}

export function useImportCommit() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rows: Record<string, string | null>[]) => api.post<ImportCommitResult>("/admin/students/import/commit", { rows }),
    onSuccess: () => invalidateStudents(queryClient),
  });
}
