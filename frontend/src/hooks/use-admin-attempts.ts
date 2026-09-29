"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AdminAttemptDetail,
  AdminAttemptRow,
  ExtraTimeIn,
  NewAttemptIn,
  Page,
  UnlockAttemptIn,
} from "@/lib/types";

export function useExamAttempts(examId: number, status: string | null, page: number, pageSize = 25) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  return useQuery<Page<AdminAttemptRow>>({
    queryKey: ["admin", "exams", examId, "attempts", status, page],
    queryFn: () => api.get<Page<AdminAttemptRow>>(`/admin/exams/${examId}/attempts?${params.toString()}`),
    placeholderData: (prev) => prev,
  });
}

export function useAttemptDetail(attemptId: number | null) {
  return useQuery<AdminAttemptDetail>({
    queryKey: ["admin", "attempts", attemptId],
    queryFn: () => api.get<AdminAttemptDetail>(`/admin/attempts/${attemptId}`),
    enabled: attemptId !== null,
  });
}

function useAttemptMutation<TArgs>(attemptId: number, fn: (args: TArgs) => Promise<AdminAttemptDetail>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      queryClient.setQueryData(["admin", "attempts", attemptId], data);
      queryClient.invalidateQueries({ queryKey: ["admin", "exams", data.exam_id, "attempts"] });
    },
  });
}

export function useUnlockAttempt(attemptId: number) {
  return useAttemptMutation(attemptId, (payload: UnlockAttemptIn) => api.post<AdminAttemptDetail>(`/admin/attempts/${attemptId}/unlock`, payload));
}

export function useGrantExtraTime(attemptId: number) {
  return useAttemptMutation(attemptId, (payload: ExtraTimeIn) => api.post<AdminAttemptDetail>(`/admin/attempts/${attemptId}/extra-time`, payload));
}

export function useGrantNewAttempt(attemptId: number) {
  return useAttemptMutation(attemptId, (payload: NewAttemptIn) => api.post<AdminAttemptDetail>(`/admin/attempts/${attemptId}/new-attempt`, payload));
}
