import Link from "next/link";
import Image from "next/image";
import { ArrowLeft, BookOpen } from "lucide-react";
import type { CourseCard as CourseCardType } from "@/lib/types";

// DESIGN.md §6 CourseCard: accent edge, subject chip, title, progress bar, lesson count, continue
// button. Accent is one of the 7 brand-safe tokens (--accent-<name>-{fg,soft,bar}), never a
// hardcoded colour.
export function CourseCard({ course }: { course: CourseCardType }) {
  return (
    <article className="flex flex-col overflow-hidden rounded-lg border border-border bg-surface shadow-[var(--shadow-1)]">
      <div className="relative h-28 bg-surface-2" style={{ background: `var(--accent-${course.accent}-soft)` }}>
        {course.cover_url ? (
          <Image src={course.cover_url} alt="" fill className="object-cover" unoptimized />
        ) : (
          <div className="flex h-full items-center justify-center text-h1 font-bold" style={{ color: `var(--accent-${course.accent}-fg)` }}>
            {course.subject.slice(0, 2)}
          </div>
        )}
        <span className="absolute inset-x-0 bottom-0 h-1" style={{ background: `var(--accent-${course.accent}-bar)` }} />
      </div>
      <div className="flex flex-1 flex-col gap-3 p-5">
        <span className="text-overline" style={{ color: `var(--accent-${course.accent}-fg)` }}>{course.subject}</span>
        <div>
          <h3 className="text-h3">{course.title}</h3>
          {course.subtitle ? <p className="mt-1 text-body-sm text-text-muted">{course.subtitle}</p> : null}
        </div>
        <span className="flex items-center gap-1.5 text-caption text-text-muted">
          <BookOpen size={15} /> {course.lesson_count} درس
        </span>
        <div className="mt-auto flex flex-col gap-2">
          <div className="flex items-center justify-between text-caption">
            <span>التقدم</span>
            <strong>{course.progress}%</strong>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${course.progress}%`, background: `var(--accent-${course.accent}-bar)` }} />
          </div>
        </div>
        <Link href={`/courses/${course.id}`} className="mt-2 flex items-center justify-center gap-1.5 rounded-md bg-primary py-2.5 text-body-sm font-medium text-primary-fg hover:bg-primary-hover">
          {course.progress > 0 ? "أكمل الكورس" : "ابدأ الآن"} <ArrowLeft size={16} className="rtl-flip" />
        </Link>
      </div>
    </article>
  );
}
