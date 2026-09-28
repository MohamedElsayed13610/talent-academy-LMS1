"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AdminExamDetail,
  AdminExamRow,
  AnswerKeyApplyIn,
  AnswerKeyPreview,
  ExamDeletePreview,
  ExamIn,
  ExamPatch,
  Page,
  QuestionPatch,
  TextQuestionIn,
} from "@/lib/types";

export interface ExamFilters {
  q?: string;
  course_id?: number;
  state?: string;
  page?: number;
  page_size?: number;
}

function toQuery(filters: ExamFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useExams(filters: ExamFilters = {}) {
  return useQuery<Page<AdminExamRow>>({
    queryKey: ["admin", "exams", filters],
    queryFn: () => api.get<Page<AdminExamRow>>(`/admin/exams${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useExam(id: number | null) {
  return useQuery<AdminExamDetail>({
    queryKey: ["admin", "exams", id],
    queryFn: () => api.get<AdminExamDetail>(`/admin/exams/${id}`),
    enabled: id !== null,
  });
}

export function useExamDeletePreview(id: number | null) {
  return useQuery<ExamDeletePreview>({
    queryKey: ["admin", "exams", id, "delete-preview"],
    queryFn: () => api.get<ExamDeletePreview>(`/admin/exams/${id}/delete-preview`),
    enabled: id !== null,
  });
}

function invalidateList(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["admin", "exams"] });
}

function useExamTreeMutation<TArgs>(examId: number, fn: (args: TArgs) => Promise<AdminExamDetail>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      queryClient.setQueryData(["admin", "exams", examId], data);
      invalidateList(queryClient);
    },
  });
}

export function useCreateExam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ExamIn) => api.post<AdminExamDetail>("/admin/exams", payload),
    onSuccess: () => invalidateList(queryClient),
    meta: { silent: true },
  });
}

export function useUpdateExam(examId: number) {
  return useExamTreeMutation(examId, (payload: ExamPatch) => api.patch<AdminExamDetail>(`/admin/exams/${examId}`, payload));
}

export function useDeleteExam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/admin/exams/${id}`),
    onSuccess: () => invalidateList(queryClient),
  });
}

export function usePublishExam(examId: number) {
  return useExamTreeMutation(examId, () => api.post<AdminExamDetail>(`/admin/exams/${examId}/publish`));
}

export function useUnpublishExam(examId: number) {
  return useExamTreeMutation(examId, () => api.post<AdminExamDetail>(`/admin/exams/${examId}/unpublish`));
}

export function useAddTextQuestion(examId: number) {
  return useExamTreeMutation(examId, (payload: TextQuestionIn) => api.post<AdminExamDetail>(`/admin/exams/${examId}/questions`, payload));
}

export function useReorderQuestions(examId: number) {
  return useExamTreeMutation(examId, (ids: number[]) => api.put<AdminExamDetail>(`/admin/exams/${examId}/questions/order`, { ids }));
}

export function useUpdateQuestion(examId: number) {
  return useExamTreeMutation(examId, ({ id, ...payload }: { id: number } & QuestionPatch) => api.patch<AdminExamDetail>(`/admin/questions/${id}`, payload));
}

export function useDeleteQuestion(examId: number) {
  return useExamTreeMutation(examId, (id: number) => api.delete<AdminExamDetail>(`/admin/questions/${id}`));
}

export interface UploadQuestionImagesArgs {
  files: File[];
  topic: string;
  difficulty: string;
  points: number;
}

export function useUploadQuestionImages(examId: number) {
  return useExamTreeMutation(examId, ({ files, topic, difficulty, points }: UploadQuestionImagesArgs) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("topic", topic);
    form.append("difficulty", difficulty);
    form.append("points", String(points));
    return api.postForm<AdminExamDetail>(`/admin/exams/${examId}/question-images`, form);
  });
}

export function usePreviewAnswerKey(examId: number) {
  return useMutation({
    mutationFn: (answers: string) => api.post<AnswerKeyPreview>(`/admin/exams/${examId}/answer-key/preview`, { answers }),
  });
}

export function useApplyAnswerKey(examId: number) {
  return useExamTreeMutation(examId, (payload: AnswerKeyApplyIn) => api.post<AdminExamDetail>(`/admin/exams/${examId}/answer-key`, payload));
}
