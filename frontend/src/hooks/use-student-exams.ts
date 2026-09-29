"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AnswerIn,
  AnswersUpsertOut,
  AttemptEventOut,
  AttemptPayload,
  ExamPreStartOut,
  ExamResult,
  StudentExamCard,
  ViolationType,
} from "@/lib/types";

export function useMyExams() {
  return useQuery<StudentExamCard[]>({
    queryKey: ["me", "exams"],
    queryFn: () => api.get<StudentExamCard[]>("/me/exams"),
  });
}

export function useExamPreStart(examId: number | null) {
  return useQuery<ExamPreStartOut>({
    queryKey: ["me", "exams", examId],
    queryFn: () => api.get<ExamPreStartOut>(`/me/exams/${examId}`),
    enabled: examId !== null,
  });
}

export function useStartExam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (examId: number) => api.post<AttemptPayload>(`/me/exams/${examId}/start`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me", "exams"] }),
  });
}

// Fetched once on runner mount to resume an in-progress attempt directly by id (e.g. after a page
// refresh) — not kept polling afterward, since the runner owns its own countdown/answers state
// from here on and only talks to the server through autosave/submit.
export function useAttempt(attemptId: number | null) {
  return useQuery<AttemptPayload>({
    queryKey: ["me", "attempts", attemptId],
    queryFn: () => api.get<AttemptPayload>(`/me/attempts/${attemptId}`),
    enabled: attemptId !== null,
    staleTime: Infinity,
    retry: false,
  });
}

export function useAutosaveAnswers(attemptId: number) {
  return useMutation({
    mutationFn: ({ clientSeq, answers }: { clientSeq: number; answers: AnswerIn[] }) =>
      api.put<AnswersUpsertOut>(`/me/attempts/${attemptId}/answers`, { client_seq: clientSeq, answers }),
    meta: { silent: true },
  });
}

export function useReportViolation(attemptId: number) {
  return useMutation({
    mutationFn: ({ type, wasOffline }: { type: ViolationType; wasOffline?: boolean }) =>
      api.post<AttemptEventOut>(`/me/attempts/${attemptId}/events`, { type, was_offline: !!wasOffline }),
    meta: { silent: true },
  });
}

export function useSubmitAttempt(attemptId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ clientSeq, answers }: { clientSeq: number; answers: AnswerIn[] }) =>
      api.post<ExamResult>(`/me/attempts/${attemptId}/submit`, { client_seq: clientSeq, answers }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me", "exams"] }),
  });
}
