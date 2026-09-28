"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { BookOpen, Plus, Search, UsersRound } from "lucide-react";
import { FormEvent, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Label } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCourses, useCreateCourse } from "@/hooks/use-courses";
import { ApiError } from "@/lib/api";
import type { CourseAccent } from "@/lib/types";

const ACCENTS: CourseAccent[] = ["blue", "navy", "sky", "teal", "gold", "violet", "rose"];

export default function AdminCoursesPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);

  const { data: courses, isLoading, error, refetch } = useCourses({ q });
  const createCourse = useCreateCourse();

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      const course = await createCourse.mutateAsync({
        title: String(form.get("title") || "").trim(),
        subtitle: String(form.get("subtitle") || "").trim(),
        subject: String(form.get("subject") || "General").trim(),
        level: String(form.get("level") || "American Diploma").trim(),
        accent: String(form.get("accent") || "blue") as CourseAccent,
        is_published: false,
      });
      setCreateOpen(false);
      router.push(`/admin/courses/${course.id}`);
    } catch {
      // surfaced via createCourse.error below
    }
  }

  return (
    <div className="talent-admin-page">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-6">
        <div>
          <span className="text-overline text-primary">COURSES</span>
          <h1 className="mt-1 text-h1">الكورسات</h1>
          <p className="mt-1 text-body-sm text-text-muted">سيتم إنشاء الكورس كمسودة، ثم تنتقل مباشرة لإضافة المحتوى.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus size={17} /> إنشاء كورس
        </Button>
      </header>

      <div className="relative mt-6 max-w-sm">
        <Search size={16} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
        <Input className="ps-9" placeholder="ابحث عن كورس..." value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      <section className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الكورسات"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-36 w-full" />)}</div>
        ) : (courses?.length || 0) === 0 ? (
          <EmptyState icon={BookOpen} title="لسه مفيش كورسات" description="أنشئ كورس وابدأ بإضافة الفصول والدروس." action={<Button onClick={() => setCreateOpen(true)}><Plus size={16} /> إنشاء كورس</Button>} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {courses?.map((course) => (
              <Link
                key={course.id}
                href={`/admin/courses/${course.id}`}
                className="flex flex-col gap-3 overflow-hidden rounded-lg border border-border bg-surface transition-shadow hover:shadow-[var(--shadow-2)]"
              >
                <div className="h-2" style={{ background: `var(--accent-${course.accent}-bar)` }} />
                <div className="flex flex-col gap-3 px-5 pb-5">
                  <div className="flex items-start justify-between">
                    <h3 className="text-h3">{course.title}</h3>
                    <Badge tone={course.is_published ? "success" : "neutral"}>{course.is_published ? "منشور" : "مسودة"}</Badge>
                  </div>
                  <span className="text-caption" style={{ color: `var(--accent-${course.accent}-fg)` }}>{course.subject} · {course.level}</span>
                  <div className="flex items-center gap-3 text-caption text-text-muted">
                    <span className="flex items-center gap-1"><BookOpen size={14} /> {course.lesson_count} درس</span>
                    <span className="flex items-center gap-1"><UsersRound size={14} /> {course.student_count} طالب</span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>إنشاء كورس جديد</DialogTitle>
            <DialogDescription>سيتم إنشاؤه كمسودة غير منشورة حتى تضيف المحتوى وتنشره بنفسك.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="title">اسم الكورس</Label>
              <Input id="title" name="title" required minLength={2} placeholder="مثال: SAT Math — Basics" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="subtitle">وصف مختصر (اختياري)</Label>
              <Input id="subtitle" name="subtitle" placeholder="Algebra • Problem Solving" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="subject">المادة</Label>
                <Input id="subject" name="subject" required defaultValue="Math" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="level">المستوى</Label>
                <Input id="level" name="level" defaultValue="American Diploma" />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>لون الكورس</Label>
              {/* Select.Root's `name` prop renders its own hidden native <select> for form
                  association (Radix), so FormData.get("accent") on submit just works. */}
              <Select name="accent" defaultValue="blue">
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ACCENTS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {createCourse.error ? <p className="text-body-sm text-danger-fg">{(createCourse.error as ApiError).message}</p> : null}
            <Button loading={createCourse.isPending}>إنشاء وفتح محرر الكورس</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
