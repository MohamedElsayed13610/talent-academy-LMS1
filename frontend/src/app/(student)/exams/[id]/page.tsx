"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, Award, CheckCircle2, Clock, FileQuestion, RotateCw } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useExamPreStart, useStartExam } from "@/hooks/use-student-exams";
import { formatCairo } from "@/lib/cairo-time";
import { ApiError } from "@/lib/api";
import type { StudentExamStatus } from "@/lib/types";

const STATUS_LABEL: Record<StudentExamStatus, string> = {
  upcoming: "قادم", available: "متاح الآن", in_progress: "جاري الآن",
  submitted: "تم التسليم", expired: "انتهى الوقت", completed: "مكتمل",
};
const STATUS_TONE: Record<StudentExamStatus, "neutral" | "info" | "success" | "danger" | "primary"> = {
  upcoming: "info", available: "success", in_progress: "primary", submitted: "neutral", expired: "danger", completed: "neutral",
};

export default function ExamPreStartPage() {
  const params = useParams<{ id: string }>();
  const examId = Number(params.id);
  const router = useRouter();
  const { data: exam, isLoading, error, refetch } = useExamPreStart(examId);
  const startExam = useStartExam();
  const [starting, setStarting] = useState(false);

  async function handleStart() {
    setStarting(true);
    try {
      const attempt = await startExam.mutateAsync(examId);
      router.push(`/exams/attempt/${attempt.attempt_id}`);
    } catch {
      setStarting(false);
      // toast already shown globally
    }
  }

  if (isLoading) return <Skeleton className="h-80 w-full" />;
  if (error || !exam) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الامتحان"} onRetry={() => refetch()} />;

  const canStart = exam.status === "available" || exam.status === "in_progress" || exam.status === "submitted";
  const actionLabel = exam.status === "in_progress" ? "استمرار المحاولة" : exam.attempts_used > 0 ? "محاولة جديدة" : "بدء الامتحان";

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/exams" className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
        <ArrowRight size={16} className="rtl-flip" /> رجوع للامتحانات
      </Link>

      <div className="mt-4 rounded-lg border border-border bg-surface p-6 shadow-[var(--shadow-1)]">
        <div className="flex items-start justify-between gap-2">
          <div>
            <span className="text-overline text-primary-soft-fg">{exam.course_title}{exam.group_name ? ` · ${exam.group_name}` : ""}</span>
            <h1 className="mt-1 text-h1">{exam.title}</h1>
          </div>
          <Badge tone={STATUS_TONE[exam.status]}>{STATUS_LABEL[exam.status]}</Badge>
        </div>

        {exam.description ? <p className="mt-3 text-body-sm text-text-muted">{exam.description}</p> : null}

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <InfoTile icon={Clock} label="المدة" value={`${exam.duration} دقيقة`} />
          <InfoTile icon={FileQuestion} label="الأسئلة" value={`${exam.question_count}`} />
          <InfoTile icon={Award} label="درجة النجاح" value={`${exam.passing_score}%`} />
          <InfoTile icon={RotateCw} label="المحاولات" value={`${exam.attempts_used}/${exam.max_attempts}`} />
        </div>

        {exam.latest ? (
          <div className="mt-4 flex items-center gap-2 rounded-md bg-surface-2 px-4 py-3 text-body-sm">
            <CheckCircle2 size={16} className={exam.latest.passed ? "text-success-fg" : "text-danger-fg"} />
            آخر نتيجة: <strong>{exam.latest.percentage}%</strong> ({exam.latest.score_points}/{exam.latest.total_points}) — {exam.latest.passed ? "ناجح" : "غير ناجح"}
            {exam.best_score !== null && exam.best_score !== exam.latest.percentage ? <span className="text-text-muted">· أعلى نتيجة: {exam.best_score}%</span> : null}
          </div>
        ) : null}

        {exam.status === "upcoming" && exam.starts_at ? (
          <div className="mt-4 flex items-center gap-2 rounded-md bg-info-soft px-4 py-3 text-body-sm text-info-fg">
            <AlertTriangle size={16} /> الامتحان يبدأ في {formatCairo(exam.starts_at)}
          </div>
        ) : null}
        {exam.status === "expired" ? (
          <div className="mt-4 flex items-center gap-2 rounded-md bg-danger-soft px-4 py-3 text-body-sm text-danger-fg">
            <AlertTriangle size={16} /> انتهى الوقت المسموح لبدء هذا الامتحان.
          </div>
        ) : null}
        {exam.status === "completed" ? (
          <div className="mt-4 flex items-center gap-2 rounded-md bg-surface-2 px-4 py-3 text-body-sm text-text-muted">
            <CheckCircle2 size={16} /> استنفذت عدد المحاولات المسموحة لهذا الامتحان.
          </div>
        ) : null}
        {exam.ends_at ? <p className="mt-3 text-caption text-text-subtle">آخر موعد: {formatCairo(exam.ends_at)}</p> : null}

        {canStart ? (
          <Button className="mt-6 w-full" size="lg" onClick={handleStart} loading={starting}>{actionLabel}</Button>
        ) : null}
      </div>
    </div>
  );
}

function InfoTile({ icon: Icon, label, value }: { icon: typeof Clock; label: string; value: string }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-md bg-surface-2 py-3 text-center">
      <Icon size={17} className="text-primary" />
      <strong className="text-body-sm">{value}</strong>
      <span className="text-caption text-text-subtle">{label}</span>
    </div>
  );
}
