"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminCourse } from "@/lib/types";

// Full course CRUD is Phase 3 — this list-only hook exists so Students/Groups pages can offer a
// course picker (ARCHITECTURE.md §6.3: "/admin/students" needs "GET /admin/courses (filter options)").
export function useCourses() {
  return useQuery<AdminCourse[]>({
    queryKey: ["admin", "courses"],
    queryFn: () => api.get<AdminCourse[]>("/admin/courses"),
    staleTime: 60_000,
  });
}
