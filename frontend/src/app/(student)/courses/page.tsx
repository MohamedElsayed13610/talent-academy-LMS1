"use client";

import { BookOpen } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { CourseCard } from "@/components/course-card";
import { useMyCourses } from "@/hooks/use-my-courses";
import { ApiError } from "@/lib/api";

export default function StudentCoursesPage() {
  const { data: courses, isLoading, error, refetch } = useMyCourses();

  return (
    <div>
      <h1 className="text-h1">كورساتي</h1>
      <p className="mt-1 text-body-sm text-text-muted">كل الكورسات المتاحة لك، مع نسبة تقدمك في كل واحد.</p>

      <div className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الكورسات"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-56 w-full" />)}</div>
        ) : (courses?.length || 0) === 0 ? (
          <EmptyState icon={BookOpen} title="لسه مفيش كورسات متاحة" description="أي كورس يضيفه الأدمن لحسابك هيظهر هنا." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {courses?.map((course) => <CourseCard key={course.id} course={course} />)}
          </div>
        )}
      </div>
    </div>
  );
}
