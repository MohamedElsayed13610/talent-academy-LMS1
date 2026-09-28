"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CourseCard, CourseDetail, LessonDetail, RecordedLessonsGroup } from "@/lib/types";

export function useMyCourses() {
  return useQuery<CourseCard[]>({
    queryKey: ["me", "courses"],
    queryFn: () => api.get<CourseCard[]>("/me/courses"),
  });
}

export function useMyCourseDetail(id: number | null) {
  return useQuery<CourseDetail>({
    queryKey: ["me", "courses", id],
    queryFn: () => api.get<CourseDetail>(`/me/courses/${id}`),
    enabled: id !== null,
  });
}

export function useMyRecordedLessons() {
  return useQuery<RecordedLessonsGroup[]>({
    queryKey: ["me", "lessons"],
    queryFn: () => api.get<RecordedLessonsGroup[]>("/me/lessons"),
  });
}

export function useMyLessonDetail(id: number | null) {
  return useQuery<LessonDetail>({
    queryKey: ["me", "lessons", id],
    queryFn: () => api.get<LessonDetail>(`/me/lessons/${id}`),
    enabled: id !== null,
  });
}

export function useUpdateLessonProgress(lessonId: number, courseId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (completed: boolean) => api.put<{ completed: boolean; points_awarded: number }>(`/me/lessons/${lessonId}/progress`, { completed }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me", "lessons"] });
      queryClient.invalidateQueries({ queryKey: ["me", "lessons", lessonId] });
      queryClient.invalidateQueries({ queryKey: ["me", "courses"] });
      queryClient.invalidateQueries({ queryKey: ["me", "courses", courseId] });
    },
  });
}
