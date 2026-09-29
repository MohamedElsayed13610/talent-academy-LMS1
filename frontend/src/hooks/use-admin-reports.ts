"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminLeaderRow, Page, PointEvent, StudentReportDetail, StudentReportRow } from "@/lib/types";

export interface StudentReportFilters {
  q?: string;
  grade?: string;
  type?: string;
  subscription?: string;
  group_id?: number;
  course_id?: number;
  sort?: string;
  page?: number;
  page_size?: number;
}

function toQuery(filters: StudentReportFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function useStudentReports(filters: StudentReportFilters = {}) {
  return useQuery<Page<StudentReportRow>>({
    queryKey: ["admin", "reports", "students", filters],
    queryFn: () => api.get<Page<StudentReportRow>>(`/admin/reports/students${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useStudentReportDetail(studentId: number | null) {
  return useQuery<StudentReportDetail>({
    queryKey: ["admin", "reports", "students", studentId],
    queryFn: () => api.get<StudentReportDetail>(`/admin/reports/students/${studentId}`),
    enabled: studentId !== null,
  });
}

export function useAdminLeaderboard(courseId: number | null, page: number = 1, pageSize: number = 25) {
  return useQuery<Page<AdminLeaderRow>>({
    queryKey: ["admin", "leaderboard", courseId, page],
    queryFn: () => api.get<Page<AdminLeaderRow>>(`/admin/leaderboard?course_id=${courseId}&page=${page}&page_size=${pageSize}`),
    enabled: courseId !== null,
    placeholderData: (prev) => prev,
  });
}

export function useAdminStudentPoints(studentId: number | null, page: number = 1, pageSize: number = 25) {
  return useQuery<Page<PointEvent>>({
    queryKey: ["admin", "students", studentId, "points", page],
    queryFn: () => api.get<Page<PointEvent>>(`/admin/students/${studentId}/points?page=${page}&page_size=${pageSize}`),
    enabled: studentId !== null,
  });
}
