"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AdminCourse,
  AdminCourseDetail,
  CourseDeletePreview,
  CourseIn,
  CoursePatch,
  CourseStudentRow,
  FileOut,
} from "@/lib/types";

export function useCourses(filters: { q?: string; published?: boolean } = {}) {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.published !== undefined) params.set("published", String(filters.published));
  const qs = params.toString();
  return useQuery<AdminCourse[]>({
    queryKey: ["admin", "courses", filters],
    queryFn: () => api.get<AdminCourse[]>(`/admin/courses${qs ? `?${qs}` : ""}`),
    staleTime: 30_000,
  });
}

export function useCourse(id: number | null) {
  return useQuery<AdminCourseDetail>({
    queryKey: ["admin", "courses", id],
    queryFn: () => api.get<AdminCourseDetail>(`/admin/courses/${id}`),
    enabled: id !== null,
  });
}

export function useCourseStudents(id: number | null) {
  return useQuery<CourseStudentRow[]>({
    queryKey: ["admin", "courses", id, "students"],
    queryFn: () => api.get<CourseStudentRow[]>(`/admin/courses/${id}/students`),
    enabled: id !== null,
  });
}

export function useDeletePreview(id: number | null) {
  return useQuery<CourseDeletePreview>({
    queryKey: ["admin", "courses", id, "delete-preview"],
    queryFn: () => api.get<CourseDeletePreview>(`/admin/courses/${id}/delete-preview`),
    enabled: id !== null,
  });
}

function invalidate(queryClient: ReturnType<typeof useQueryClient>, id?: number) {
  queryClient.invalidateQueries({ queryKey: ["admin", "courses"] });
  if (id) queryClient.invalidateQueries({ queryKey: ["admin", "courses", id] });
}

export function useCreateCourse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CourseIn) => api.post<AdminCourseDetail>("/admin/courses", payload),
    onSuccess: () => invalidate(queryClient),
    meta: { silent: true }, // rendered inline in the create-course dialog
  });
}

export function useUpdateCourse(id: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CoursePatch) => api.patch<AdminCourseDetail>(`/admin/courses/${id}`, payload),
    onSuccess: () => invalidate(queryClient, id),
  });
}

export function useDeleteCourse() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, cascade }: { id: number; cascade?: boolean }) => api.delete(`/admin/courses/${id}${cascade ? "?cascade=true" : ""}`),
    onSuccess: () => invalidate(queryClient),
  });
}

function useCourseTreeMutation<TArgs>(id: number, fn: (args: TArgs) => Promise<AdminCourseDetail>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data) => {
      queryClient.setQueryData(["admin", "courses", id], data);
      invalidate(queryClient);
    },
  });
}

export function useAddSection(courseId: number) {
  return useCourseTreeMutation(courseId, (title: string) => api.post<AdminCourseDetail>(`/admin/courses/${courseId}/sections`, { title }));
}
export function useUpdateSection(courseId: number) {
  return useCourseTreeMutation(courseId, ({ id, title }: { id: number; title: string }) => api.patch<AdminCourseDetail>(`/admin/sections/${id}`, { title }));
}
export function useDeleteSection(courseId: number) {
  return useCourseTreeMutation(courseId, (id: number) => api.delete<AdminCourseDetail>(`/admin/sections/${id}`));
}
export function useReorderSections(courseId: number) {
  return useCourseTreeMutation(courseId, (ids: number[]) => api.put<AdminCourseDetail>(`/admin/courses/${courseId}/sections/order`, { ids }));
}

export function useAddLesson(courseId: number) {
  return useCourseTreeMutation(courseId, ({ sectionId, ...payload }: { sectionId: number; title: string; description?: string; duration_minutes?: number; recording_url?: string | null; is_preview?: boolean }) =>
    api.post<AdminCourseDetail>(`/admin/sections/${sectionId}/lessons`, payload));
}
export function useUpdateLesson(courseId: number) {
  return useCourseTreeMutation(courseId, ({ id, ...payload }: { id: number; title?: string; description?: string; duration_minutes?: number; recording_url?: string | null; is_preview?: boolean }) =>
    api.patch<AdminCourseDetail>(`/admin/lessons/${id}`, payload));
}
export function useDeleteLesson(courseId: number) {
  return useCourseTreeMutation(courseId, (id: number) => api.delete<AdminCourseDetail>(`/admin/lessons/${id}`));
}
export function useReorderLessons(courseId: number) {
  return useCourseTreeMutation(courseId, ({ sectionId, ids }: { sectionId: number; ids: number[] }) => api.put<AdminCourseDetail>(`/admin/sections/${sectionId}/lessons/order`, { ids }));
}

export function useAddMaterial(courseId: number) {
  return useCourseTreeMutation(courseId, ({ lessonId, ...payload }: { lessonId: number; title: string; material_type: string; url?: string | null; file_id?: string | null; is_downloadable?: boolean }) =>
    api.post<AdminCourseDetail>(`/admin/lessons/${lessonId}/materials`, payload));
}
export function useDeleteMaterial(courseId: number) {
  return useCourseTreeMutation(courseId, (id: number) => api.delete<AdminCourseDetail>(`/admin/materials/${id}`));
}

export function useUploadFile() {
  return useMutation({
    mutationFn: ({ file, purpose }: { file: File; purpose: string }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("purpose", purpose);
      return api.postForm<FileOut>("/admin/files", form);
    },
  });
}
