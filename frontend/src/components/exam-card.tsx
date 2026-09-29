import Link from "next/link";
import { ArrowLeft, Clock, FileQuestion, Trophy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatCairo } from "@/lib/cairo-time";
import type { StudentExamCard, StudentExamStatus } from "@/lib/types";

const STATUS_LABEL: Record<StudentExamStatus, string> = {
  upcoming: "قادم", available: "متاح الآن", in_progress: "جاري الآن",
  submitted: "تم التسليم", expired: "انتهى الوقت", completed: "مكتمل",
};
const STATUS_TONE: Record<StudentExamStatus, "neutral" | "info" | "success" | "danger" | "primary"> = {
  upcoming: "info", available: "success", in_progress: "primary", submitted: "neutral", expired: "danger", completed: "neutral",
};

export function ExamCard({ exam }: { exam: StudentExamCard }) {
  return (
    <Link href={`/exams/${exam.id}`} className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-5 shadow-[var(--shadow-1)] transition-colors hover:border-border-strong">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="text-overline text-primary-soft-fg">{exam.course_title}{exam.group_name ? ` · ${exam.group_name}` : ""}</span>
          <h3 className="mt-1 text-h3">{exam.title}</h3>
        </div>
        <Badge tone={STATUS_TONE[exam.status]}>{STATUS_LABEL[exam.status]}</Badge>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-caption text-text-muted">
        <span className="flex items-center gap-1.5"><Clock size={14} /> {exam.duration} دقيقة</span>
        <span className="flex items-center gap-1.5"><FileQuestion size={14} /> {exam.question_count} سؤال</span>
        <span>محاولات: {exam.attempts_used}/{exam.max_attempts}</span>
      </div>

      {exam.best_score !== null ? (
        <span className="flex items-center gap-1.5 text-body-sm">
          <Trophy size={15} className="text-accent-fg" /> أعلى نتيجة: <strong>{exam.best_score}%</strong>
        </span>
      ) : null}

      {exam.status === "upcoming" && exam.starts_at ? (
        <span className="text-caption text-text-subtle">يبدأ: {formatCairo(exam.starts_at)}</span>
      ) : exam.ends_at ? (
        <span className="text-caption text-text-subtle">ينتهي: {formatCairo(exam.ends_at)}</span>
      ) : null}

      <span className="mt-1 flex items-center gap-1.5 text-body-sm font-medium text-primary">
        {exam.status === "in_progress" ? "استمرار المحاولة" : "عرض التفاصيل"} <ArrowLeft size={15} className="rtl-flip" />
      </span>
    </Link>
  );
}
