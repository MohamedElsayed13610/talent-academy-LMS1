"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AcademySettingsOut,
  AcademySettingsUpdate,
  AdminAccountCreate,
  AdminAccountCreateResponse,
  AdminAccountOut,
  AdminAccountUpdate,
  AuditLogRow,
  BackupStatusOut,
  Page,
} from "@/lib/types";

export function useAcademySettings() {
  return useQuery<AcademySettingsOut>({
    queryKey: ["admin", "settings"],
    queryFn: () => api.get<AcademySettingsOut>("/admin/settings"),
  });
}

export function useUpdateAcademySettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AcademySettingsUpdate) => api.put<AcademySettingsOut>("/admin/settings", payload),
    onSuccess: (data) => {
      queryClient.setQueryData(["admin", "settings"], data);
      queryClient.invalidateQueries({ queryKey: ["public", "branding"] });
    },
  });
}

export function useBackupStatus() {
  return useQuery<BackupStatusOut>({
    queryKey: ["admin", "settings", "backup"],
    queryFn: () => api.get<BackupStatusOut>("/admin/settings/backup"),
  });
}

export function useAdminAccounts() {
  return useQuery<AdminAccountOut[]>({
    queryKey: ["admin", "admins"],
    queryFn: () => api.get<AdminAccountOut[]>("/admin/admins"),
  });
}

export function useCreateAdminAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminAccountCreate) => api.post<AdminAccountCreateResponse>("/admin/admins", payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "admins"] }),
  });
}

export function useUpdateAdminAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: AdminAccountUpdate }) => api.patch<AdminAccountOut>(`/admin/admins/${id}`, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "admins"] }),
  });
}

export function useDeleteAdminAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/admin/admins/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "admins"] }),
  });
}

export function useAuditLog(page: number = 1, pageSize: number = 25) {
  return useQuery<Page<AuditLogRow>>({
    queryKey: ["admin", "audit-log", page],
    queryFn: () => api.get<Page<AuditLogRow>>(`/admin/audit-log?page=${page}&page_size=${pageSize}`),
    placeholderData: (prev) => prev,
  });
}
