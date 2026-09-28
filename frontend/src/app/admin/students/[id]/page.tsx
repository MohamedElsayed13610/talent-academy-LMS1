"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, BookOpen, KeyRound, Plus, Trash2, UsersRound, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";
import { StudentFormFields } from "@/components/students/student-form";
import { useCourses } from "@/hooks/use-courses";
import {
  useDeletePreview,
  useDeleteStudent,
  useEnrollStudent,
  useRemoveEnrollment,
  useResetPassword,
  useStudent,
  useUpdateStudent,
} from "@/hooks/use-students";
import { ApiError } from "@/lib/api";

export default function StudentDetailPage() {
  const params = useParams<{ id: string }>();
  const studentId = Number(params.id);
  const router = useRouter();

  const { data: student, isLoading, error, refetch } = useStudent(studentId);
  const { data: courses } = useCourses();
  const updateStudent = useUpdateStudent(studentId);
  const deleteStudent = useDeleteStudent();
  const resetPassword = useResetPassword();
  const enroll = useEnrollStudent();
  const removeEnrollment = useRemoveEnrollment();
  const deletePreview = useDeletePreview(studentId);

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [generatedPassword, setGeneratedPassword] = useState<string | null>(null);
  const [courseToAdd, setCourseToAdd] = useState("");

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (error || !student) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل بيانات الطالب"} onRetry={() => refetch()} />;

  async function handleUpdate(payload: Parameters<typeof updateStudent.mutateAsync>[0]) {
    try {
      await updateStudent.mutateAsync(payload);
      toast.success("تم حفظ التعديلات");
    } catch {
      // rendered inline via StudentFormFields' `error` prop (hooks/use-students.ts marks it silent)
    }
  }

  async function handleReset() {
    try {
      const result = await resetPassword.mutateAsync({ id: studentId });
      if (result.generated_password) setGeneratedPassword(result.generated_password);
      else toast.success("تم تحديث كلمة المرور");
    } catch {
      // toast already shown globally (app/providers.tsx MutationCache)
    }
  }

  async function handleDelete() {
    const name = student?.full_name ?? "";
    try {
      await deleteStudent.mutateAsync(studentId);
      toast.success(`تم حذف ${name}`);
      router.push("/admin/students");
    } catch {
      // toast already shown globally
    }
  }

  async function addCourse() {
    if (!courseToAdd) return;
    try {
      await enroll.mutateAsync({ studentId, courseId: Number(courseToAdd) });
      setCourseToAdd("");
      toast.success("تم إضافة الكورس");
    } catch {
      // toast already shown globally
    }
  }

  const availableCourses = (courses || []).filter((c) => !student.enrollments.some((e) => e.course_id === c.id));

  return (
    <div className="talent-admin-page max-w-3xl">
      <Link href="/admin/students" className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
        <ArrowRight size={16} className="rtl-flip" /> رجوع للطلاب
      </Link>

      <header className="mt-3 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-6">
        <div>
          <h1 className="text-h1">{student.full_name}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-caption ltr">{student.student_code}</span>
            {student.grade_level ? <Badge tone="neutral">{student.grade_level}</Badge> : null}
            <StatusBadge value={student.student_type} />
            <StatusBadge value={student.effective_subscription} />
            <StatusBadge value={student.is_active} />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={handleReset} loading={resetPassword.isPending}>
            <KeyRound size={16} /> إعادة تعيين كلمة المرور
          </Button>
          <Button variant="danger" onClick={() => setConfirmDelete(true)}>
            <Trash2 size={16} /> حذف
          </Button>
        </div>
      </header>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><UsersRound size={17} /> المجموعات</CardTitle>
            <CardDescription>{student.groups.length ? `${student.groups.length} مجموعة` : "بدون مجموعة"}</CardDescription>
          </CardHeader>
          <div className="flex flex-wrap gap-1.5">
            {student.groups.map((g) => <Badge key={g.id} tone="primary">{g.name}</Badge>)}
          </div>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><BookOpen size={17} /> الكورسات</CardTitle>
            <CardDescription>{student.enrollments.length} كورس ({student.enrollments.filter((e) => e.source === "group").length} عبر مجموعة)</CardDescription>
          </CardHeader>
          <div className="flex flex-col gap-2">
            {student.enrollments.map((e) => (
              <div key={e.course_id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-body-sm">
                <span>{e.course_title}{e.source === "group" ? <span className="text-caption"> (عبر مجموعة)</span> : null}</span>
                {e.source === "direct" ? (
                  <button onClick={() => removeEnrollment.mutate({ studentId, courseId: e.course_id })} className="text-text-subtle hover:text-danger-fg" aria-label="إزالة">
                    <X size={15} />
                  </button>
                ) : null}
              </div>
            ))}
            {availableCourses.length > 0 ? (
              <div className="mt-2 flex items-center gap-2">
                <Select value={courseToAdd} onValueChange={setCourseToAdd}>
                  <SelectTrigger><SelectValue placeholder="إضافة كورس..." /></SelectTrigger>
                  <SelectContent>
                    {availableCourses.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.title}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Button size="sm" onClick={addCourse} disabled={!courseToAdd}><Plus size={15} /></Button>
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>بيانات الطالب</CardTitle>
        </CardHeader>
        <StudentFormFields mode="edit" initial={student} onSubmit={handleUpdate} loading={updateStudent.isPending} error={updateStudent.error as ApiError | null} />
      </Card>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`حذف ${student.full_name}`}
        destructive
        loading={deleteStudent.isPending}
        onConfirm={handleDelete}
        description={
          deletePreview.data ? (
            <span>
              سيتم حذف كل بياناته نهائيًا: {deletePreview.data.enrollments} اشتراك، {deletePreview.data.groups} مجموعة،{" "}
              {deletePreview.data.attempts} محاولة امتحان، {deletePreview.data.attendance} حضور، {deletePreview.data.points} نقاط.
            </span>
          ) : "جارٍ التحميل..."
        }
      />

      {generatedPassword ? (
        <Dialog open onOpenChange={() => setGeneratedPassword(null)}>
          <div className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-surface-raised p-6 text-center shadow-[var(--shadow-3)]">
            <h2 className="text-h2">كلمة المرور الجديدة</h2>
            <p className="mt-1 text-body-sm text-text-muted">احفظها الآن — لن تظهر مرة أخرى.</p>
            <p className="ltr mt-4 rounded-md bg-surface-2 py-3 text-h1 tracking-wider">{generatedPassword}</p>
            <Button className="mt-4 w-full" onClick={() => setGeneratedPassword(null)}>تم</Button>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}
