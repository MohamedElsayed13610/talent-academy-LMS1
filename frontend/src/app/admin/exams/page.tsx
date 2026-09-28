"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FileText, Plus, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Label } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCairo } from "@/lib/cairo-time";
import { useCourses } from "@/hooks/use-courses";
import { useCreateExam, useExams, type ExamFilters } from "@/hooks/use-exams";
import { ApiError } from "@/lib/api";

const ALL = "__all__";
const STATE_LABEL: Record<string, string> = { draft: "مسودة", upcoming: "قادم", available: "متاح", ended: "انتهى" };
const STATE_TONE: Record<string, "neutral" | "info" | "success" | "danger"> = { draft: "neutral", upcoming: "info", available: "success", ended: "danger" };

export default function AdminExamsPage() {
  const router = useRouter();
  const [filters, setFilters] = useState<ExamFilters>({ page: 1, page_size: 25 });
  const [createOpen, setCreateOpen] = useState(false);

  const { data, isLoading, error, refetch } = useExams(filters);
  const { data: courses } = useCourses();
  const createExam = useCreateExam();

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      const exam = await createExam.mutateAsync({
        title: String(form.get("title") || "").trim(),
        course_id: Number(form.get("course_id")),
        exam_mode: String(form.get("exam_mode") || "answer_sheet") as "full" | "answer_sheet",
        duration_minutes: Number(form.get("duration_minutes") || 30),
        passing_score: Number(form.get("passing_score") || 50),
        max_attempts: Number(form.get("max_attempts") || 1),
      });
      setCreateOpen(false);
      router.push(`/admin/exams/${exam.id}`);
    } catch {
      // surfaced via createExam.error below
    }
  }

  return (
    <div className="talent-admin-page">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-6">
        <div>
          <span className="text-overline text-primary">EXAMS</span>
          <h1 className="mt-1 text-h1">الامتحانات</h1>
          <p className="mt-1 text-body-sm text-text-muted">يُنشأ الامتحان كمسودة، ثم تنتقل مباشرة لإضافة الأسئلة.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}><Plus size={17} /> إنشاء امتحان</Button>
      </header>

      <section className="mt-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search size={16} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
          <Input className="ps-9" placeholder="ابحث عن امتحان..." defaultValue={filters.q} onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value, page: 1 }))} />
        </div>
        <Select value={filters.state || ALL} onValueChange={(v) => setFilters((f) => ({ ...f, state: v === ALL ? undefined : v, page: 1 }))}>
          <SelectTrigger className="w-36"><SelectValue placeholder="الحالة" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الحالات</SelectItem>
            <SelectItem value="draft">مسودة</SelectItem>
            <SelectItem value="upcoming">قادم</SelectItem>
            <SelectItem value="available">متاح</SelectItem>
            <SelectItem value="ended">انتهى</SelectItem>
          </SelectContent>
        </Select>
        <Select value={filters.course_id ? String(filters.course_id) : ALL} onValueChange={(v) => setFilters((f) => ({ ...f, course_id: v === ALL ? undefined : Number(v), page: 1 }))}>
          <SelectTrigger className="w-48"><SelectValue placeholder="الكورس" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الكورسات</SelectItem>
            {(courses || []).map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.title}</SelectItem>)}
          </SelectContent>
        </Select>
      </section>

      <section className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الامتحانات"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="flex flex-col gap-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full" />)}</div>
        ) : (data?.items.length || 0) === 0 ? (
          <EmptyState icon={FileText} title="لا توجد امتحانات" description="أنشئ أول امتحان." action={<Button onClick={() => setCreateOpen(true)}><Plus size={16} /> إنشاء امتحان</Button>} />
        ) : (
          <>
            <div className="flex flex-col gap-2">
              {data?.items.map((exam) => (
                <Link key={exam.id} href={`/admin/exams/${exam.id}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4 hover:shadow-[var(--shadow-1)]">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-h3">{exam.title}</h3>
                      <Badge tone={STATE_TONE[exam.state]}>{STATE_LABEL[exam.state]}</Badge>
                      {exam.group_name ? <Badge tone="neutral">{exam.group_name}</Badge> : null}
                    </div>
                    <p className="mt-1 text-caption text-text-muted">
                      {exam.course_title} · {exam.question_count} سؤال · {exam.total_points} نقطة
                      {exam.starts_at ? ` · يبدأ ${formatCairo(exam.starts_at)}` : ""}
                    </p>
                  </div>
                  <div className="text-end text-caption text-text-muted">
                    <div>{exam.attempts_count} محاولة</div>
                    {exam.average_score !== null ? <div>متوسط {Math.round(exam.average_score)}%</div> : null}
                    {exam.locked_count > 0 ? <div className="text-danger-fg">{exam.locked_count} مقفلة</div> : null}
                  </div>
                </Link>
              ))}
            </div>
            <div className="mt-4">
              <Pagination page={data?.page || 1} pageSize={data?.page_size || 25} total={data?.total || 0} onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))} />
            </div>
          </>
        )}
      </section>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>إنشاء امتحان جديد</DialogTitle>
            <DialogDescription>سيتم إنشاؤه كمسودة غير منشورة حتى تضيف الأسئلة وتنشره بنفسك.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="title">عنوان الامتحان</Label>
              <Input id="title" name="title" required minLength={2} placeholder="مثال: EST English Unit 3" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="course_id">الكورس</Label>
              <select id="course_id" name="course_id" required defaultValue="" className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
                <option value="" disabled>اختر كورس</option>
                {(courses || []).map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="exam_mode">نوع الامتحان</Label>
                <select id="exam_mode" name="exam_mode" defaultValue="answer_sheet" className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
                  <option value="answer_sheet">ورقة إجابة (bubble sheet)</option>
                  <option value="full">أسئلة كاملة</option>
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="duration_minutes">المدة (دقيقة)</Label>
                <Input id="duration_minutes" name="duration_minutes" type="number" min={1} max={600} defaultValue={30} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="passing_score">درجة النجاح (%)</Label>
                <Input id="passing_score" name="passing_score" type="number" min={0} max={100} defaultValue={50} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="max_attempts">عدد المحاولات</Label>
                <Input id="max_attempts" name="max_attempts" type="number" min={1} max={10} defaultValue={1} />
              </div>
            </div>
            {createExam.error ? <p className="text-body-sm text-danger-fg">{(createExam.error as ApiError).message}</p> : null}
            <Button loading={createExam.isPending}>إنشاء وفتح محرر الامتحان</Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
