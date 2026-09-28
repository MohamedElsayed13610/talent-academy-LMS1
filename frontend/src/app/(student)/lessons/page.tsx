"use client";

import Link from "next/link";
import { CheckCircle2, Circle, PlayCircle } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyRecordedLessons } from "@/hooks/use-my-courses";
import { ApiError } from "@/lib/api";

export default function RecordedLessonsPage() {
  const { data: groups, isLoading, error, refetch } = useMyRecordedLessons();

  return (
    <div>
      <h1 className="text-h1">الدروس المسجلة</h1>
      <p className="mt-1 text-body-sm text-text-muted">كل الدروس مجمّعة حسب الكورس.</p>

      <div className="mt-6 flex flex-col gap-4">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الدروس"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="flex flex-col gap-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-40 w-full" />)}</div>
        ) : (groups?.length || 0) === 0 ? (
          <EmptyState icon={PlayCircle} title="لا توجد دروس مسجلة بعد" description="الدروس المسجلة لكورساتك هتظهر هنا." />
        ) : (
          groups?.map((group) => (
            <div key={group.course_id} className="rounded-lg border border-border bg-surface">
              <div className="border-b border-border px-5 py-3">
                <h2 className="text-h3">{group.course_title}</h2>
              </div>
              <div className="flex flex-col divide-y divide-border">
                {group.lessons.map((lesson) => (
                  <Link key={lesson.id} href={`/courses/${group.course_id}/lessons/${lesson.id}`} className="flex items-center justify-between gap-3 px-5 py-3.5 text-body-sm hover:bg-surface-2">
                    <span className="flex items-center gap-3">
                      {lesson.completed ? <CheckCircle2 size={19} className="text-success-fg" /> : <Circle size={19} className="text-text-subtle" />}
                      {lesson.title}
                    </span>
                    <span className="text-caption text-text-muted">{lesson.duration_minutes} د</span>
                  </Link>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
