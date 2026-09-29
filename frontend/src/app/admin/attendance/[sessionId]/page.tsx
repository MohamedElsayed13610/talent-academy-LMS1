"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, Check, Download, MessageSquare, Pencil, Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAttendanceSheet, useFinalizeAttendance, useUpdateAttendance } from "@/hooks/use-live-sessions";
import { api, ApiError, saveBlob } from "@/lib/api";
import type { AttendanceRow, AttendanceStatus } from "@/lib/types";

const STATUSES: { value: Exclude<AttendanceStatus, "unmarked">; label: string }[] = [
  { value: "present", label: "حاضر" },
  { value: "late", label: "متأخر" },
  { value: "absent", label: "غائب" },
  { value: "excused", label: "بعذر" },
];

export default function AttendanceSheetPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = Number(params.sessionId);
  const [q, setQ] = useState("");
  const [noteTarget, setNoteTarget] = useState<AttendanceRow | null>(null);
  const [confirmFinalize, setConfirmFinalize] = useState(false);
  const [pendingStudentId, setPendingStudentId] = useState<number | null>(null);
  const [unlockedForEdit, setUnlockedForEdit] = useState(false);

  const { data: sheet, isLoading, error, refetch } = useAttendanceSheet(sessionId);
  const updateAttendance = useUpdateAttendance(sessionId);
  const finalizeAttendance = useFinalizeAttendance(sessionId);

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (error || !sheet) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل شاشة الحضور"} onRetry={() => refetch()} />;

  const { session, counts } = sheet;
  const students = sheet.students.filter((s) => !q || s.full_name.includes(q) || (s.student_code || "").toLowerCase().includes(q.toLowerCase()));

  async function setStatus(studentId: number, status: string, note?: string) {
    setPendingStudentId(studentId);
    try {
      await updateAttendance.mutateAsync({ studentId, status, note });
    } catch {
      // toast already shown globally
    } finally {
      setPendingStudentId(null);
    }
  }

  async function handleFinalize() {
    try {
      await finalizeAttendance.mutateAsync();
      toast.success("تم اعتماد الحضور والغياب");
      setConfirmFinalize(false);
    } catch {
      // toast already shown globally
    }
  }

  async function exportXlsx() {
    try {
      const { blob, filename } = await api.getBlob(`/admin/live-sessions/${sessionId}/attendance.xlsx`);
      saveBlob(blob, filename || "attendance.xlsx");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر تصدير الملف");
    }
  }

  return (
    <div className="talent-admin-page">
      <Link href="/admin/attendance" className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
        <ArrowRight size={16} className="rtl-flip" /> رجوع لاختيار الحصة
      </Link>

      <header className="mt-3 border-b border-border pb-4">
        <h1 className="text-h1">{session.title}</h1>
        <p className="mt-1 text-body-sm text-text-muted">{session.course_title}{session.group_name ? ` · ${session.group_name}` : ""} · {new Date(session.starts_at).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" })}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-body-sm">
          <Badge tone="success">حاضر {counts.present}</Badge>
          <Badge tone="warning">متأخر {counts.late}</Badge>
          <Badge tone="danger">غائب {counts.absent}</Badge>
          <Badge tone="info">بعذر {counts.excused}</Badge>
          <Badge tone="neutral">غير محدد {counts.unmarked}</Badge>
        </div>
      </header>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="relative max-w-xs flex-1">
          <Search size={16} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
          <Input className="ps-9" placeholder="بحث بالاسم أو الكود..." value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={exportXlsx}><Download size={15} /> تصدير Excel</Button>
          {!session.attendance_finalized_at ? (
            <Button
              size="sm"
              onClick={() => setConfirmFinalize(true)}
              disabled={counts.unmarked > 0}
              title={counts.unmarked > 0 ? `لازم تحدد حالة ${counts.unmarked} طالب الأول` : undefined}
            >
              اعتماد الحضور والغياب
            </Button>
          ) : (
            <>
              <Badge tone="success"><Check size={13} /> تم اعتماد الحضور والغياب</Badge>
              {!unlockedForEdit ? (
                <Button variant="secondary" size="sm" onClick={() => setUnlockedForEdit(true)}>
                  <Pencil size={14} /> تعديل السجل
                </Button>
              ) : (
                <Badge tone="warning">وضع التعديل مفعّل</Badge>
              )}
            </>
          )}
        </div>
      </div>
      {session.attendance_finalized_at && counts.unmarked > 0 ? (
        <p className="mt-2 text-caption text-warning-fg">تنبيه: يوجد {counts.unmarked} طالب بدون حالة رغم اعتماد الحضور — راجع السجل.</p>
      ) : null}

      <div className="mt-4 flex flex-col gap-2">
        {students.map((row) => (
          <div key={row.student_id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3.5">
            <div className="min-w-[160px]">
              <p className="text-body-sm font-medium text-text">{row.full_name}</p>
              <p className="text-caption text-text-muted ltr">{row.student_code}</p>
              {row.joined_at ? (
                <p className="mt-0.5 text-caption text-success-fg">
                  دخل {new Date(row.joined_at).toLocaleTimeString("ar-EG", { hour: "2-digit", minute: "2-digit" })} ✓ {row.source === "self_join" ? "تلقائي" : "عُدّل بواسطة الإدارة"}
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {STATUSES.map((s) => (
                <button
                  key={s.value}
                  disabled={pendingStudentId === row.student_id || (!!session.attendance_finalized_at && !unlockedForEdit)}
                  onClick={() => setStatus(row.student_id, row.status === s.value ? "unmarked" : s.value)}
                  className={`h-11 min-w-[70px] rounded-md border px-3 text-body-sm font-medium transition-colors disabled:opacity-50 ${
                    row.status === s.value
                      ? s.value === "present" ? "border-success-fg bg-success-soft text-success-fg"
                      : s.value === "late" ? "border-warning-fg bg-warning-soft text-warning-fg"
                      : s.value === "absent" ? "border-danger-fg bg-danger-soft text-danger-fg"
                      : "border-info-fg bg-info-soft text-info-fg"
                      : "border-border hover:bg-surface-2"
                  }`}
                >
                  {s.label}
                </button>
              ))}
              <button onClick={() => setNoteTarget(row)} className="flex size-11 items-center justify-center rounded-md border border-border text-text-muted hover:bg-surface-2" aria-label="ملاحظة">
                <MessageSquare size={16} className={row.note ? "text-primary" : ""} />
              </button>
            </div>
          </div>
        ))}
        {students.length === 0 ? <p className="py-8 text-center text-body-sm text-text-muted">لا نتائج.</p> : null}
      </div>

      <Dialog open={!!noteTarget} onOpenChange={(open) => !open && setNoteTarget(null)}>
        {noteTarget ? (
          <DialogContent className="max-w-sm">
            <DialogHeader>
              <DialogTitle>ملاحظة عن {noteTarget.full_name}</DialogTitle>
            </DialogHeader>
            <form
              className="flex flex-col gap-3"
              onSubmit={async (e) => {
                e.preventDefault();
                const note = String(new FormData(e.currentTarget).get("note") || "");
                await setStatus(noteTarget.student_id, noteTarget.status, note);
                setNoteTarget(null);
              }}
            >
              <textarea name="note" defaultValue={noteTarget.note} rows={3} className="rounded-md border border-border bg-surface p-3 text-body-sm" />
              <Button loading={pendingStudentId === noteTarget.student_id}>حفظ</Button>
            </form>
          </DialogContent>
        ) : null}
      </Dialog>

      <ConfirmDialog
        open={confirmFinalize}
        onOpenChange={setConfirmFinalize}
        title="اعتماد الحضور والغياب"
        confirmLabel="اعتماد"
        loading={finalizeAttendance.isPending}
        onConfirm={handleFinalize}
        description="سيتم اعتماد حالة الحضور لكل الطلاب كما هي معروضة الآن. يمكنك تعديل السجل لاحقًا عبر زر «تعديل السجل»."
      />
    </div>
  );
}
