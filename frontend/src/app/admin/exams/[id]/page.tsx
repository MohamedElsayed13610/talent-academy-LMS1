"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, CheckCircle2, Lock, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useCourses } from "@/hooks/use-courses";
import { useGroups } from "@/hooks/use-groups";
import { useDeleteExam, useExam, useExamDeletePreview, usePublishExam, useUnpublishExam, useUpdateExam } from "@/hooks/use-exams";
import { toCairoInputValue, fromCairoInputValue } from "@/lib/cairo-time";
import { ApiError } from "@/lib/api";
import type { AdminExamDetail } from "@/lib/types";
import { QuestionsTab } from "./questions-tab";
import { AnswerKeyTab } from "./answer-key-tab";

const STATE_LABEL: Record<string, string> = { draft: "مسودة", upcoming: "قادم", available: "متاح", ended: "انتهى" };
const STATE_TONE: Record<string, "neutral" | "info" | "success" | "danger"> = { draft: "neutral", upcoming: "info", available: "success", ended: "danger" };

export default function ExamBuilderPage() {
  const params = useParams<{ id: string }>();
  const examId = Number(params.id);
  const router = useRouter();

  const { data: exam, isLoading, error, refetch } = useExam(examId);
  const deleteExam = useDeleteExam();
  const deletePreview = useExamDeletePreview(examId);
  const publishExam = usePublishExam(examId);
  const unpublishExam = useUnpublishExam(examId);

  const [confirmDelete, setConfirmDelete] = useState(false);

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (error || !exam) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الامتحان"} onRetry={() => refetch()} />;

  const readyToPublish = exam.question_count > 0 && exam.questions.every((q) => q.choices.filter((c) => c.is_correct).length === 1);
  const notReadyQuestions = exam.questions.filter((q) => q.choices.filter((c) => c.is_correct).length !== 1).map((q) => q.position);

  async function togglePublish() {
    try {
      if (exam!.is_published) {
        await unpublishExam.mutateAsync();
        toast.success("تم إلغاء نشر الامتحان");
      } else {
        await publishExam.mutateAsync();
        toast.success("تم نشر الامتحان");
      }
    } catch {
      // toast already shown globally (also surfaces EXAM_NOT_READY with question numbers)
    }
  }

  async function handleDelete() {
    try {
      await deleteExam.mutateAsync(examId);
      toast.success(`تم حذف ${exam!.title}`);
      router.push("/admin/exams");
    } catch {
      // toast already shown globally
    }
  }

  return (
    <div className="talent-admin-page max-w-5xl">
      <Link href="/admin/exams" className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
        <ArrowRight size={16} className="rtl-flip" /> رجوع للامتحانات
      </Link>

      <header className="mt-3 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-6">
        <div>
          <h1 className="text-h1">{exam.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge tone={STATE_TONE[exam.state]}>{STATE_LABEL[exam.state]}</Badge>
            <span className="text-caption text-text-muted">{exam.course_title}{exam.group_name ? ` · ${exam.group_name}` : ""}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant={exam.is_published ? "secondary" : "primary"} onClick={togglePublish} loading={publishExam.isPending || unpublishExam.isPending} disabled={!exam.is_published && !readyToPublish}>
            {exam.is_published ? "إلغاء النشر" : "نشر الامتحان"}
          </Button>
          <Button variant="danger" onClick={() => setConfirmDelete(true)}><Trash2 size={16} /> حذف</Button>
        </div>
      </header>

      <div className="mt-4 flex items-center gap-3 rounded-lg border border-border bg-surface-2 px-4 py-3 text-body-sm">
        <span className="flex items-center gap-1.5">
          {exam.question_count > 0 ? <CheckCircle2 size={16} className="text-success-fg" /> : <AlertTriangle size={16} className="text-warning-fg" />}
          الأسئلة: {exam.question_count}
        </span>
        <span className="flex items-center gap-1.5">
          {readyToPublish ? <CheckCircle2 size={16} className="text-success-fg" /> : <AlertTriangle size={16} className="text-warning-fg" />}
          مفتاح الإجابة: {readyToPublish ? "جاهز" : `${notReadyQuestions.length} سؤال بدون إجابة صحيحة`}
        </span>
        <span className="flex items-center gap-1.5">
          {exam.is_published ? <CheckCircle2 size={16} className="text-success-fg" /> : <AlertTriangle size={16} className="text-text-subtle" />}
          {exam.is_published ? "منشور" : "غير منشور"}
        </span>
      </div>

      {exam.has_attempts ? (
        <div className="mt-4 flex items-center gap-2 rounded-lg bg-info-soft px-4 py-3 text-body-sm text-info-fg">
          <Lock size={16} />
          بدأ طلاب في أداء هذا الامتحان — الأسئلة والدرجات والإجابات الصحيحة مجمّدة الآن ولا يمكن تعديلها. تقدر تعدّل الموضوع والصعوبة ونص السؤال فقط.
        </div>
      ) : null}

      <Tabs defaultValue="settings" dir="rtl" className="mt-6">
        <TabsList>
          <TabsTrigger value="settings">الإعدادات</TabsTrigger>
          <TabsTrigger value="questions">الأسئلة ({exam.question_count})</TabsTrigger>
          <TabsTrigger value="answer-key">مفتاح الإجابة</TabsTrigger>
        </TabsList>

        <TabsContent value="settings" className="mt-5">
          <SettingsTab exam={exam} />
        </TabsContent>
        <TabsContent value="questions" className="mt-5">
          <QuestionsTab exam={exam} />
        </TabsContent>
        <TabsContent value="answer-key" className="mt-5">
          <AnswerKeyTab exam={exam} />
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`حذف ${exam.title}`}
        destructive
        loading={deleteExam.isPending}
        onConfirm={handleDelete}
        description={
          deletePreview.data ? (
            <span>
              سيتم حذف {deletePreview.data.questions} سؤال نهائيًا.
              {deletePreview.data.attempts > 0 ? (
                <strong className="mt-2 block text-danger-fg">
                  تحذير: {deletePreview.data.attempts} محاولة طالب و{deletePreview.data.points_entries} حركة نقاط مرتبطة بهذا الامتحان هيتم حذفها أيضًا.
                </strong>
              ) : null}
            </span>
          ) : "جارٍ التحميل..."
        }
      />
    </div>
  );
}

function SettingsTab({ exam }: { exam: AdminExamDetail }) {
  const updateExam = useUpdateExam(exam.id);
  const { data: courses } = useCourses();
  const { data: groupsPage } = useGroups();

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const groupValue = String(form.get("group_id") || "");
    const startsValue = String(form.get("starts_at") || "");
    const endsValue = String(form.get("ends_at") || "");
    try {
      await updateExam.mutateAsync({
        title: String(form.get("title") || "").trim(),
        description: String(form.get("description") || "").trim(),
        course_id: Number(form.get("course_id")),
        group_id: groupValue ? Number(groupValue) : null,
        exam_mode: String(form.get("exam_mode") || "answer_sheet") as "full" | "answer_sheet",
        duration_minutes: Number(form.get("duration_minutes") || 30),
        passing_score: Number(form.get("passing_score") || 50),
        max_attempts: Number(form.get("max_attempts") || 1),
        starts_at: startsValue ? fromCairoInputValue(startsValue) : null,
        ends_at: endsValue ? fromCairoInputValue(endsValue) : null,
      });
      toast.success("تم حفظ الإعدادات");
    } catch {
      // toast already shown globally
    }
  }

  return (
    <form onSubmit={submit} className="flex max-w-2xl flex-col gap-4 rounded-lg border border-border bg-surface p-6">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="title">عنوان الامتحان</Label>
        <Input id="title" name="title" required minLength={2} defaultValue={exam.title} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="description">الوصف</Label>
        <Textarea id="description" name="description" rows={3} defaultValue={exam.description} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="course_id">الكورس</Label>
          <select id="course_id" name="course_id" required defaultValue={exam.course_id} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            {(courses || []).map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="group_id">مجموعة محددة (اختياري)</Label>
          <select id="group_id" name="group_id" defaultValue={exam.group_id || ""} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            <option value="">كل طلاب الكورس</option>
            {(groupsPage?.items || []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="exam_mode">نوع الامتحان</Label>
          <select id="exam_mode" name="exam_mode" defaultValue={exam.exam_mode} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            <option value="answer_sheet">ورقة إجابة</option>
            <option value="full">أسئلة كاملة</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="duration_minutes">المدة (دقيقة)</Label>
          <Input id="duration_minutes" name="duration_minutes" type="number" min={1} max={600} defaultValue={exam.duration_minutes} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="passing_score">درجة النجاح (%)</Label>
          <Input id="passing_score" name="passing_score" type="number" min={0} max={100} defaultValue={exam.passing_score} />
        </div>
      </div>
      <div className="flex flex-col gap-1.5 max-w-[200px]">
        <Label htmlFor="max_attempts">عدد المحاولات المسموحة</Label>
        <Input id="max_attempts" name="max_attempts" type="number" min={1} max={10} defaultValue={exam.max_attempts} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="starts_at">يبدأ (بتوقيت القاهرة)</Label>
          <Input id="starts_at" name="starts_at" type="datetime-local" defaultValue={toCairoInputValue(exam.starts_at)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="ends_at">ينتهي (بتوقيت القاهرة)</Label>
          <Input id="ends_at" name="ends_at" type="datetime-local" defaultValue={toCairoInputValue(exam.ends_at)} />
        </div>
      </div>
      {updateExam.error ? <p className="text-body-sm text-danger-fg">{(updateExam.error as ApiError).message}</p> : null}
      <Button className="self-start" loading={updateExam.isPending}>حفظ الإعدادات</Button>
    </form>
  );
}
