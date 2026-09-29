"use client";

import { FileQuestion } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ExamCard } from "@/components/exam-card";
import { useMyExams } from "@/hooks/use-student-exams";
import { ApiError } from "@/lib/api";

export default function StudentExamsPage() {
  const { data: exams, isLoading, error, refetch } = useMyExams();

  return (
    <div>
      <h1 className="text-h1">الامتحانات</h1>
      <p className="mt-1 text-body-sm text-text-muted">كل الامتحانات المتاحة لك، ونتائج محاولاتك السابقة.</p>

      <div className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الامتحانات"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-48 w-full" />)}</div>
        ) : (exams?.length || 0) === 0 ? (
          <EmptyState icon={FileQuestion} title="لا يوجد امتحانات متاحة الآن" description="أي امتحان يفعّله الأدمن لكورساتك هيظهر هنا." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {exams?.map((exam) => <ExamCard key={exam.id} exam={exam} />)}
          </div>
        )}
      </div>
    </div>
  );
}
