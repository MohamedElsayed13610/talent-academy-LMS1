"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, CheckCircle2, Circle, PlayCircle } from "lucide-react";
import { ErrorState } from "@/components/ui/error-state";
import { ProgressRing } from "@/components/ui/progress-ring";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyCourseDetail } from "@/hooks/use-my-courses";
import { ApiError } from "@/lib/api";

export default function StudentCourseDetailPage() {
  const params = useParams<{ id: string }>();
  const courseId = Number(params.id);
  const { data, isLoading, error, refetch } = useMyCourseDetail(courseId);

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (error || !data) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الكورس"} onRetry={() => refetch()} />;

  const { course, sections } = data;

  return (
    <div>
      <Link href="/courses" className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
        <ArrowRight size={16} className="rtl-flip" /> كل الكورسات
      </Link>

      <header className="mt-3 flex flex-wrap items-center justify-between gap-4 border-b border-border pb-6">
        <div>
          <span className="text-overline" style={{ color: `var(--accent-${course.accent}-fg)` }}>{course.subject} · {course.level}</span>
          <h1 className="mt-1 text-h1">{course.title}</h1>
          {course.subtitle ? <p className="mt-1 text-body-sm text-text-muted">{course.subtitle}</p> : null}
        </div>
        <ProgressRing value={course.progress} size={72} />
      </header>

      <div className="mt-6 flex flex-col gap-4">
        {sections.map((section) => (
          <div key={section.id} className="rounded-lg border border-border bg-surface">
            <div className="border-b border-border px-5 py-3">
              <h2 className="text-h3">{section.title}</h2>
            </div>
            <div className="flex flex-col divide-y divide-border">
              {section.lessons.map((lesson) => (
                <Link
                  key={lesson.id}
                  href={`/courses/${course.id}/lessons/${lesson.id}`}
                  className="flex items-center justify-between gap-3 px-5 py-3.5 text-body-sm hover:bg-surface-2"
                >
                  <span className="flex items-center gap-3">
                    {lesson.completed ? <CheckCircle2 size={19} className="text-success-fg" /> : <Circle size={19} className="text-text-subtle" />}
                    <span className="flex items-center gap-1.5">
                      {lesson.has_recording ? <PlayCircle size={15} className="text-text-subtle" /> : null}
                      {lesson.title}
                    </span>
                    {lesson.is_preview ? <span className="rounded-full bg-info-soft px-2 py-0.5 text-caption text-info-fg">تعريفي</span> : null}
                  </span>
                  <span className="text-caption text-text-muted">{lesson.duration_minutes} د</span>
                </Link>
              ))}
              {section.lessons.length === 0 ? <p className="px-5 py-4 text-body-sm text-text-muted">لا يوجد دروس في هذا الفصل بعد.</p> : null}
            </div>
          </div>
        ))}
        {sections.length === 0 ? <p className="py-10 text-center text-body-sm text-text-muted">لا يوجد محتوى في هذا الكورس بعد.</p> : null}
      </div>
    </div>
  );
}
