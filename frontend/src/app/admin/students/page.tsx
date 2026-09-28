"use client";

import Link from "next/link";
import {
  Download,
  FileSpreadsheet,
  KeyRound,
  Search,
  Trash2,
  UserCog,
  UserPlus,
  UsersRound,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StudentFormDrawer } from "@/components/students/student-form";
import { StatusBadge } from "@/components/status-badge";
import { useGroups } from "@/hooks/use-groups";
import {
  useBulkAction,
  useCreateStudent,
  useDeletePreview,
  useDeleteStudent,
  useResetPassword,
  useStudents,
  type StudentFilters,
} from "@/hooks/use-students";
import { api, ApiError, saveBlob } from "@/lib/api";
import type { StudentRow } from "@/lib/types";

const GRADES = ["G10", "G11", "G12"] as const;
const ALL = "__all__";

export default function AdminStudentsPage() {
  const [filters, setFilters] = useState<StudentFilters>({ page: 1, page_size: 25 });
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [createOpen, setCreateOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<StudentRow | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<StudentRow | null>(null);
  const [generatedPassword, setGeneratedPassword] = useState<{ name: string; password: string } | null>(null);
  const [bulkGroupOpen, setBulkGroupOpen] = useState(false);

  const { data, isLoading, error, refetch } = useStudents(filters);
  const { data: groupsPage } = useGroups();
  const createStudent = useCreateStudent();
  const deleteStudent = useDeleteStudent();
  const resetPassword = useResetPassword();
  const bulkAction = useBulkAction();
  const deletePreview = useDeletePreview(deleteTarget?.id ?? null);

  const students = data?.items || [];
  // Derived, not synced via an effect: the group-picker dialog can only be opened from the
  // bulk-action bar (itself hidden once selected.size is 0), but if the selection empties out
  // while it's still open (e.g. the user deselected everyone), this closes it on the next render
  // instead of letting a stale "open" state allow a request with an empty student_ids.
  const groupDialogOpen = bulkGroupOpen && selected.size > 0;

  function toggleAll() {
    if (selected.size === students.length) setSelected(new Set());
    else setSelected(new Set(students.map((s) => s.id)));
  }
  function toggleOne(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleCreate(payload: Parameters<typeof createStudent.mutateAsync>[0]) {
    try {
      const result = await createStudent.mutateAsync(payload);
      setCreateOpen(false);
      if (result.generated_password) {
        setGeneratedPassword({ name: result.student.full_name, password: result.generated_password });
      } else {
        toast.success("تم إنشاء حساب الطالب");
      }
    } catch {
      // error surfaces via createStudent.error in the form
    }
  }

  async function handleReset(password?: string) {
    if (!resetTarget) return;
    try {
      const result = await resetPassword.mutateAsync({ id: resetTarget.id, password });
      if (result.generated_password) setGeneratedPassword({ name: resetTarget.full_name, password: result.generated_password });
      else toast.success("تم تحديث كلمة المرور");
      setResetTarget(null);
    } catch {
      // toast already shown globally (app/providers.tsx MutationCache)
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteStudent.mutateAsync(deleteTarget.id);
      toast.success(`تم حذف ${deleteTarget.full_name}`);
      setDeleteTarget(null);
    } catch {
      // toast already shown globally
    }
  }

  // Both bulk actions guard against an empty selection before calling the API at all — the bar
  // that exposes them is already hidden when nothing is selected, but this covers the dialog
  // still being open after the selection changed underneath it (e.g. the user deselected
  // everyone while "إضافة لمجموعة" was open).
  async function runBulk(action: "activate" | "deactivate" | "delete") {
    if (selected.size === 0) return;
    try {
      const result = await bulkAction.mutateAsync({ student_ids: [...selected], action });
      toast.success(`تم تنفيذ الإجراء على ${result.affected} طالب`);
      setSelected(new Set());
    } catch {
      // toast already shown globally
    }
  }

  async function addSelectedToGroup(groupId: number) {
    if (selected.size === 0) {
      toast.error("لم يتم تحديد أي طالب");
      setBulkGroupOpen(false);
      return;
    }
    try {
      const result = await bulkAction.mutateAsync({ student_ids: [...selected], action: "add_to_group", group_id: groupId });
      toast.success(`تمت إضافة ${result.affected} طالب للمجموعة`);
      setSelected(new Set());
      setBulkGroupOpen(false);
    } catch {
      // toast already shown globally
    }
  }

  async function exportExcel() {
    try {
      const { blob, filename } = await api.getBlob(`/admin/students/export.xlsx`);
      saveBlob(blob, filename || "students.xlsx");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر تصدير الملف");
    }
  }

  return (
    <div className="talent-admin-page">
      <header className="flex flex-col justify-between gap-4 border-b border-border pb-6 sm:flex-row sm:items-center">
        <div>
          <span className="text-overline text-primary">STUDENTS</span>
          <h1 className="mt-1 text-h1">الطلاب</h1>
          <p className="mt-1 text-body-sm text-text-muted">أدخل Student ID كما هو في شيت الأكاديمية. الصف بيانات فقط ولا يضيف الطالب تلقائيًا لأي كورس.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={exportExcel}>
            <Download size={17} /> تصدير Excel
          </Button>
          <Button variant="secondary" asChild>
            <Link href="/admin/students/import">
              <FileSpreadsheet size={17} /> استيراد Excel
            </Link>
          </Button>
          <Button onClick={() => setCreateOpen(true)}>
            <UserPlus size={17} /> إضافة طالب
          </Button>
        </div>
      </header>

      <section className="mt-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search size={16} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
          <Input
            className="ps-9"
            placeholder="ابحث بالاسم أو Student ID أو البريد..."
            defaultValue={filters.q}
            onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value, page: 1 }))}
          />
        </div>
        <Select value={filters.grade || ALL} onValueChange={(v) => setFilters((f) => ({ ...f, grade: v === ALL ? undefined : v, page: 1 }))}>
          <SelectTrigger className="w-36"><SelectValue placeholder="الصف" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الصفوف</SelectItem>
            {GRADES.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.type || ALL} onValueChange={(v) => setFilters((f) => ({ ...f, type: v === ALL ? undefined : v, page: 1 }))}>
          <SelectTrigger className="w-40"><SelectValue placeholder="النوع" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الأنواع</SelectItem>
            <SelectItem value="academy">طالب الأكاديمية</SelectItem>
            <SelectItem value="external">طالب خارجي</SelectItem>
          </SelectContent>
        </Select>
        <Select value={filters.subscription || ALL} onValueChange={(v) => setFilters((f) => ({ ...f, subscription: v === ALL ? undefined : v, page: 1 }))}>
          <SelectTrigger className="w-44"><SelectValue placeholder="الاشتراك" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الحالات</SelectItem>
            <SelectItem value="active">نشط</SelectItem>
            <SelectItem value="pending">قيد الانتظار</SelectItem>
            <SelectItem value="expired">منتهي</SelectItem>
            <SelectItem value="suspended">موقوف</SelectItem>
          </SelectContent>
        </Select>
      </section>

      {selected.size > 0 ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-md bg-primary-soft px-4 py-3">
          <span className="text-body-sm font-medium text-primary-soft-fg">{selected.size} محدد</span>
          <Button size="sm" variant="secondary" onClick={() => setBulkGroupOpen(true)}><UsersRound size={15} /> إضافة لمجموعة</Button>
          <Button size="sm" variant="secondary" onClick={() => runBulk("activate")}>تفعيل</Button>
          <Button size="sm" variant="secondary" onClick={() => runBulk("deactivate")}>إيقاف</Button>
          <Button size="sm" variant="danger" onClick={() => { if (confirm(`حذف ${selected.size} طالب نهائيًا؟`)) runBulk("delete"); }}>
            <Trash2 size={15} /> حذف
          </Button>
        </div>
      ) : null}

      <section className="mt-4">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الطلاب"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="flex flex-col gap-2">{[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
        ) : students.length === 0 ? (
          <EmptyState icon={UsersRound} title="لسه مفيش طلاب" description="أضف طالب أو استورد قائمة من Excel." action={<Button onClick={() => setCreateOpen(true)}><UserPlus size={16} /> إضافة طالب</Button>} />
        ) : (
          <>
            <div className="hidden overflow-x-auto rounded-lg border border-border lg:block">
              <table className="w-full text-body-sm">
                <thead className="bg-surface-2 text-caption text-text-muted">
                  <tr>
                    <th className="w-10 p-3"><Checkbox checked={selected.size === students.length} onCheckedChange={toggleAll} /></th>
                    <th className="p-3 text-start">الطالب</th>
                    <th className="p-3 text-start ltr">Student ID</th>
                    <th className="p-3 text-start">الصف</th>
                    <th className="p-3 text-start">النوع</th>
                    <th className="p-3 text-start">الاشتراك</th>
                    <th className="p-3 text-start">المجموعات</th>
                    <th className="p-3 text-start">الحساب</th>
                    <th className="p-3 text-start">إجراء</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((s) => (
                    <tr key={s.id} className="border-t border-border">
                      <td className="p-3"><Checkbox checked={selected.has(s.id)} onCheckedChange={() => toggleOne(s.id)} /></td>
                      <td className="p-3">
                        <Link href={`/admin/students/${s.id}`} className="font-medium text-text hover:text-primary">{s.full_name}</Link>
                      </td>
                      <td className="p-3 ltr text-text-muted">{s.student_code || "—"}</td>
                      <td className="p-3">{s.grade_level ? <Badge tone="neutral">{s.grade_level}</Badge> : <span className="text-text-subtle">—</span>}</td>
                      <td className="p-3"><StatusBadge value={s.student_type} /></td>
                      <td className="p-3"><StatusBadge value={s.effective_subscription} /></td>
                      <td className="p-3 text-text-muted">{s.groups_count}</td>
                      <td className="p-3"><StatusBadge value={s.is_active} /></td>
                      <td className="p-3">
                        <div className="flex items-center gap-1">
                          <Button variant="ghost" size="sm" asChild title="تعديل"><Link href={`/admin/students/${s.id}`}><UserCog size={15} /></Link></Button>
                          <Button variant="ghost" size="sm" onClick={() => setResetTarget(s)} title="إعادة تعيين كلمة المرور"><KeyRound size={15} /></Button>
                          <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(s)} title="حذف"><Trash2 size={15} className="text-danger-fg" /></Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col gap-3 lg:hidden">
              {students.map((s) => (
                <div key={s.id} className="rounded-lg border border-border bg-surface p-4">
                  <div className="flex items-start justify-between gap-2">
                    <Checkbox checked={selected.has(s.id)} onCheckedChange={() => toggleOne(s.id)} />
                    <Link href={`/admin/students/${s.id}`} className="flex-1 font-medium text-text">{s.full_name}</Link>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className="text-caption ltr">{s.student_code}</span>
                    {s.grade_level ? <Badge tone="neutral">{s.grade_level}</Badge> : null}
                    <StatusBadge value={s.effective_subscription} />
                  </div>
                  <div className="mt-3 flex items-center gap-1">
                    <Button variant="secondary" size="sm" asChild><Link href={`/admin/students/${s.id}`}>تعديل</Link></Button>
                    <Button variant="secondary" size="sm" onClick={() => setResetTarget(s)}>كلمة المرور</Button>
                    <Button variant="danger" size="sm" onClick={() => setDeleteTarget(s)}>حذف</Button>
                  </div>
                </div>
              ))}
            </div>

            <Pagination page={data?.page || 1} pageSize={data?.page_size || 25} total={data?.total || 0} onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))} />
          </>
        )}
      </section>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <StudentFormDrawer mode="create" loading={createStudent.isPending} error={createStudent.error as ApiError | null} onSubmit={handleCreate} />
      </Dialog>

      <Dialog open={groupDialogOpen} onOpenChange={setBulkGroupOpen}>
        <div className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-surface-raised p-6 shadow-[var(--shadow-3)]">
          <h2 className="text-h2">إضافة {selected.size} طالب لمجموعة</h2>
          <div className="mt-4 flex flex-col gap-2">
            {(groupsPage?.items || []).map((g) => (
              <button key={g.id} onClick={() => addSelectedToGroup(g.id)} className="rounded-md border border-border px-3.5 py-2.5 text-start text-body-sm hover:bg-surface-2">
                {g.name}
              </button>
            ))}
          </div>
        </div>
      </Dialog>

      <ResetPasswordDialog target={resetTarget} onClose={() => setResetTarget(null)} onReset={handleReset} loading={resetPassword.isPending} />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`حذف ${deleteTarget?.full_name || ""}`}
        destructive
        loading={deleteStudent.isPending}
        onConfirm={handleDelete}
        description={
          deletePreview.data ? (
            <span>
              سيتم حذف كل بياناته نهائيًا: {deletePreview.data.enrollments} اشتراك كورس، {deletePreview.data.groups} عضوية مجموعة،{" "}
              {deletePreview.data.attempts} محاولة امتحان، {deletePreview.data.attendance} سجل حضور، {deletePreview.data.points} حركة نقاط.
              كود الطالب هيبقى متاح للاستخدام تاني فورًا.
            </span>
          ) : (
            "جارٍ تحميل البيانات..."
          )
        }
      />

      {generatedPassword ? (
        <Dialog open onOpenChange={() => setGeneratedPassword(null)}>
          <div className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-surface-raised p-6 text-center shadow-[var(--shadow-3)]">
            <h2 className="text-h2">كلمة مرور {generatedPassword.name}</h2>
            <p className="mt-1 text-body-sm text-text-muted">احفظها الآن — لن تظهر مرة أخرى.</p>
            <p className="ltr mt-4 rounded-md bg-surface-2 py-3 text-h1 tracking-wider">{generatedPassword.password}</p>
            <Button className="mt-4 w-full" onClick={() => setGeneratedPassword(null)}>تم</Button>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}

function ResetPasswordDialog({ target, onClose, onReset, loading }: { target: StudentRow | null; onClose: () => void; onReset: (password?: string) => void; loading: boolean }) {
  return (
    <Dialog open={!!target} onOpenChange={(open) => !open && onClose()}>
      {target ? (
        <div className="fixed left-1/2 top-1/2 z-50 w-[92vw] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-surface-raised p-6 shadow-[var(--shadow-3)]">
          <h2 className="text-h2">إعادة تعيين كلمة مرور {target.full_name}</h2>
          <p className="mt-1 text-body-sm text-text-muted">اتركها فارغة لتوليد كلمة مرور تلقائيًا.</p>
          <form
            className="mt-4 flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              const password = String(new FormData(e.currentTarget).get("password") || "").trim();
              onReset(password || undefined);
            }}
          >
            <Input name="password" dir="ltr" minLength={8} placeholder="كلمة مرور جديدة (اختياري)" />
            <Button loading={loading}>تأكيد</Button>
          </form>
        </div>
      ) : null}
    </Dialog>
  );
}
