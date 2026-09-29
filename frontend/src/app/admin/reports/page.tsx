"use client";

import { Download, Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCourses } from "@/hooks/use-courses";
import { useStudentReportDetail, useStudentReports, type StudentReportFilters } from "@/hooks/use-admin-reports";
import { api, ApiError, saveBlob } from "@/lib/api";
import { formatCairo } from "@/lib/cairo-time";

const GRADES = ["G10", "G11", "G12"] as const;
const ALL = "__all__";

export default function AdminReportsPage() {
  const [filters, setFilters] = useState<StudentReportFilters>({ page: 1, page_size: 25 });
  const [openStudentId, setOpenStudentId] = useState<number | null>(null);
  const { data, isLoading, error, refetch } = useStudentReports(filters);
  const { data: courses } = useCourses();

  async function exportExcel() {
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "" && k !== "page" && k !== "page_size") params.set(k, String(v)); });
      const qs = params.toString();
      const { blob, filename } = await api.getBlob(`/admin/reports/students.xlsx${qs ? `?${qs}` : ""}`);
      saveBlob(blob, filename || "students-report.xlsx");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر تصدير التقرير");
    }
  }

  return (
    <div className="talent-admin-page">
      <header className="flex flex-col justify-between gap-4 border-b border-border pb-6 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-h1">تقارير الطلاب</h1>
          <p className="mt-1 text-body-sm text-text-muted">تقدم كل طالب، حضوره، امتحاناته، ونقاطه.</p>
        </div>
        <Button variant="secondary" onClick={exportExcel}><Download size={17} /> تصدير Excel</Button>
      </header>

      <section className="mt-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search size={16} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
          <Input className="ps-9" placeholder="ابحث بالاسم أو Student ID..." onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value, page: 1 }))} />
        </div>
        <Select value={filters.grade || ALL} onValueChange={(v) => setFilters((f) => ({ ...f, grade: v === ALL ? undefined : v, page: 1 }))}>
          <SelectTrigger className="w-36"><SelectValue placeholder="الصف" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الصفوف</SelectItem>
            {GRADES.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.course_id ? String(filters.course_id) : ALL} onValueChange={(v) => setFilters((f) => ({ ...f, course_id: v === ALL ? undefined : Number(v), page: 1 }))}>
          <SelectTrigger className="w-48"><SelectValue placeholder="الكورس" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الكورسات</SelectItem>
            {(courses || []).map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.title}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.sort || "name"} onValueChange={(v) => setFilters((f) => ({ ...f, sort: v, page: 1 }))}>
          <SelectTrigger className="w-40"><SelectValue placeholder="الترتيب" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="name">الاسم</SelectItem>
            <SelectItem value="points">أعلى النقاط</SelectItem>
            <SelectItem value="-points">أقل النقاط</SelectItem>
          </SelectContent>
        </Select>
      </section>

      <div className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل التقرير"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="flex flex-col gap-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
        ) : (data?.items.length || 0) === 0 ? (
          <EmptyState icon={Search} title="لا يوجد نتائج" description="جرّب تغيير الفلاتر." />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-body-sm">
              <thead className="bg-surface-2 text-caption text-text-muted">
                <tr>
                  <th className="p-3 text-start">الطالب</th>
                  <th className="p-3 text-start">التقدم</th>
                  <th className="p-3 text-start">الدروس</th>
                  <th className="p-3 text-start">الامتحانات</th>
                  <th className="p-3 text-start">الحضور</th>
                  <th className="p-3 text-start">النقاط</th>
                  <th className="p-3 text-start">آخر دخول</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((row) => (
                  <tr key={row.student.id} className="cursor-pointer border-t border-border hover:bg-surface-2" onClick={() => setOpenStudentId(row.student.id)}>
                    <td className="p-3">
                      <div className="font-medium">{row.student.full_name}</div>
                      <div className="text-caption text-text-subtle">{row.student.student_code} · {row.student.grade_level || "—"}</div>
                    </td>
                    <td className="p-3">{row.overall_progress}%</td>
                    <td className="p-3">{row.completed_lessons}/{row.total_lessons}</td>
                    <td className="p-3">{row.exams_taken} {row.exam_average !== null ? `(${row.exam_average}%)` : ""}</td>
                    <td className="p-3">{row.attendance.rate}%</td>
                    <td className="p-3"><Badge tone="primary">{row.total_points}</Badge></td>
                    <td className="p-3 text-caption text-text-subtle">{row.last_login_at ? formatCairo(row.last_login_at) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data ? <div className="mt-3"><Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))} /></div> : null}
      </div>

      <Dialog open={openStudentId !== null} onOpenChange={(open) => !open && setOpenStudentId(null)}>
        {openStudentId !== null ? <StudentReportDialog studentId={openStudentId} /> : null}
      </Dialog>
    </div>
  );
}

function StudentReportDialog({ studentId }: { studentId: number }) {
  const { data: detail, isLoading, error } = useStudentReportDetail(studentId);

  async function exportOne() {
    try {
      const { blob, filename } = await api.getBlob(`/admin/reports/students/${studentId}.xlsx`);
      saveBlob(blob, filename || `student-${studentId}-report.xlsx`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر تصدير التقرير");
    }
  }

  if (isLoading || !detail) {
    return (
      <DialogContent>
        <DialogHeader><DialogTitle>تقرير الطالب</DialogTitle></DialogHeader>
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل التقرير"} /> : <Skeleton className="h-64 w-full" />}
      </DialogContent>
    );
  }

  return (
    <DialogContent className="max-w-2xl">
      <DialogHeader>
        <DialogTitle>{detail.student.full_name}</DialogTitle>
        <DialogDescription>{detail.student.student_code} · {detail.student.grade_level || "—"} · {detail.subscription}</DialogDescription>
      </DialogHeader>

      <div className="flex max-h-[70vh] flex-col gap-5 overflow-y-auto">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="الحضور" value={`${detail.attendance.rate}%`} />
          <Stat label="النقاط" value={String(detail.points_total)} />
          <Stat label="المجموعات" value={String(detail.groups.length)} />
          <Stat label="آخر دخول" value={detail.last_login_at ? formatCairo(detail.last_login_at) : "—"} />
        </div>

        {detail.groups.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">{detail.groups.map((g) => <Badge key={g.id} tone="info">{g.name}</Badge>)}</div>
        ) : null}

        <section>
          <h4 className="text-label text-text-muted">الكورسات</h4>
          <div className="mt-2 flex flex-col gap-1.5">
            {detail.courses.map((c) => (
              <div key={c.course_id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-body-sm">
                <span>{c.course_title}</span>
                <span className="flex items-center gap-2 text-text-muted">
                  <span>{c.progress}% تقدم</span>
                  <Badge tone="primary">#{c.rank}</Badge>
                  <span>{c.points} نقطة</span>
                </span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h4 className="text-label text-text-muted">الامتحانات</h4>
          <div className="mt-2 flex flex-col gap-1.5">
            {detail.exams.length === 0 ? <p className="text-body-sm text-text-muted">لم يبدأ أي امتحان بعد.</p> : detail.exams.map((e) => (
              <div key={e.exam_id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-body-sm">
                <span>{e.exam_title}</span>
                <span className="text-text-muted">أفضل: {e.best_percentage ?? "—"}% · آخر: {e.latest_percentage ?? "—"}% · {e.attempts_used} محاولة</span>
              </div>
            ))}
          </div>
        </section>

        {detail.admin_notes ? (
          <section>
            <h4 className="text-label text-text-muted">ملاحظات الإدارة</h4>
            <p className="mt-1 text-body-sm">{detail.admin_notes}</p>
          </section>
        ) : null}

        <Button variant="secondary" className="self-start" onClick={exportOne}><Download size={15} /> تصدير تقرير الطالب</Button>
      </div>
    </DialogContent>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-surface-2 px-3 py-2 text-center">
      <div className="text-body-sm font-semibold">{value}</div>
      <div className="text-caption text-text-subtle">{label}</div>
    </div>
  );
}
