"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, GraduationCap, Plus, Search, Trash2, UserPlus, UsersRound, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCourses } from "@/hooks/use-courses";
import { useAddByGrade, useAddMembers, useAssignCourse, useGroup, useGroupMembers, useRemoveCourse, useRemoveMember } from "@/hooks/use-groups";
import { useStudents } from "@/hooks/use-students";
import { ApiError } from "@/lib/api";

const GRADES = ["G10", "G11", "G12"] as const;

export default function GroupDetailPage() {
  const params = useParams<{ id: string }>();
  const groupId = Number(params.id);

  const { data: group, isLoading, error, refetch } = useGroup(groupId);
  const { data: members } = useGroupMembers(groupId);
  const { data: courses } = useCourses();
  const addMembers = useAddMembers(groupId);
  const removeMember = useRemoveMember(groupId);
  const addByGrade = useAddByGrade(groupId);
  const assignCourse = useAssignCourse(groupId);
  const removeCourse = useRemoveCourse(groupId);

  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [gradeOpen, setGradeOpen] = useState(false);
  const [gradeChoice, setGradeChoice] = useState<string>("G10");
  const [gradePreviewCount, setGradePreviewCount] = useState<number | null>(null);
  const [courseToAssign, setCourseToAssign] = useState("");

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (error || !group) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل المجموعة"} onRetry={() => refetch()} />;

  async function previewGrade() {
    const result = await addByGrade.mutateAsync({ gradeLevel: gradeChoice, dryRun: true });
    setGradePreviewCount(result.would_add ?? 0);
  }

  async function confirmGrade() {
    const result = await addByGrade.mutateAsync({ gradeLevel: gradeChoice, dryRun: false });
    toast.success(`تمت إضافة ${result.added ?? 0} طالب`);
    setGradeOpen(false);
    setGradePreviewCount(null);
  }

  async function assignSelectedCourse() {
    if (!courseToAssign) return;
    await assignCourse.mutateAsync({ courseId: Number(courseToAssign) });
    setCourseToAssign("");
    toast.success("تم إسناد الكورس للمجموعة");
  }

  const availableCourses = (courses || []).filter((c) => !group.courses.some((gc) => gc.id === c.id));

  return (
    <div className="talent-admin-page max-w-3xl">
      <Link href="/admin/groups" className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
        <ArrowRight size={16} className="rtl-flip" /> رجوع للمجموعات
      </Link>

      <header className="mt-3 border-b border-border pb-6">
        <h1 className="text-h1">{group.name}</h1>
        {group.description ? <p className="mt-1 text-body-sm text-text-muted">{group.description}</p> : null}
      </header>

      <Card className="mt-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2"><UsersRound size={17} /> الأعضاء</CardTitle>
              <CardDescription>{group.members_count} طالب</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setGradeOpen(true)}><GraduationCap size={15} /> إضافة صف كامل</Button>
              <Button size="sm" onClick={() => setAddMemberOpen(true)}><UserPlus size={15} /> إضافة طالب</Button>
            </div>
          </div>
        </CardHeader>
        <div className="flex flex-col gap-2">
          {(members?.items || []).map((m) => (
            <div key={m.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-body-sm">
              <span>{m.full_name} <span className="text-caption ltr">({m.student_code})</span></span>
              <button onClick={() => removeMember.mutate(m.id)} className="text-text-subtle hover:text-danger-fg" aria-label="إزالة">
                <X size={15} />
              </button>
            </div>
          ))}
          {(members?.items.length || 0) === 0 ? <p className="text-body-sm text-text-muted">لا يوجد أعضاء بعد.</p> : null}
        </div>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>الكورسات المسندة للمجموعة</CardTitle>
          <CardDescription>كل عضو في المجموعة يحصل على وصول لهذه الكورسات تلقائيًا.</CardDescription>
        </CardHeader>
        <div className="flex flex-col gap-2">
          {group.courses.map((c) => (
            <div key={c.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-body-sm">
              <span>{c.title}</span>
              <button onClick={() => removeCourse.mutate(c.id)} className="text-text-subtle hover:text-danger-fg" aria-label="إزالة"><Trash2 size={15} /></button>
            </div>
          ))}
          {availableCourses.length > 0 ? (
            <div className="mt-2 flex items-center gap-2">
              <Select value={courseToAssign} onValueChange={setCourseToAssign}>
                <SelectTrigger><SelectValue placeholder="إسناد كورس..." /></SelectTrigger>
                <SelectContent>
                  {availableCourses.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.title}</SelectItem>)}
                </SelectContent>
              </Select>
              <Button size="sm" onClick={assignSelectedCourse} disabled={!courseToAssign}><Plus size={15} /></Button>
            </div>
          ) : null}
        </div>
      </Card>

      <AddMemberDialog open={addMemberOpen} onOpenChange={setAddMemberOpen} groupId={groupId} onAdd={(id) => addMembers.mutate([id])} existingIds={new Set((members?.items || []).map((m) => m.id))} />

      <Dialog open={gradeOpen} onOpenChange={(open) => { setGradeOpen(open); if (!open) setGradePreviewCount(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>إضافة كل طلاب صف للمجموعة</DialogTitle>
            <DialogDescription>إجراء صريح — هيضيف كل طلاب الصف المختار غير الموجودين بالفعل.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <Select value={gradeChoice} onValueChange={(v) => { setGradeChoice(v); setGradePreviewCount(null); }}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {GRADES.map((g) => <SelectItem key={g} value={g}>{g}</SelectItem>)}
              </SelectContent>
            </Select>
            {gradePreviewCount === null ? (
              <Button onClick={previewGrade} loading={addByGrade.isPending}>معاينة العدد</Button>
            ) : (
              <>
                <p className="text-body-sm">سيتم إضافة <strong>{gradePreviewCount}</strong> طالب جديد لهذه المجموعة.</p>
                <Button onClick={confirmGrade} loading={addByGrade.isPending} disabled={gradePreviewCount === 0}>تأكيد الإضافة</Button>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function AddMemberDialog({ open, onOpenChange, onAdd, existingIds }: { open: boolean; onOpenChange: (open: boolean) => void; groupId: number; onAdd: (id: number) => void; existingIds: Set<number> }) {
  const [q, setQ] = useState("");
  const { data } = useStudents({ q, page: 1, page_size: 10 });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>إضافة طالب للمجموعة</DialogTitle>
          <DialogDescription>ابحث بالاسم أو Student ID.</DialogDescription>
        </DialogHeader>
        <div className="relative">
          <Search size={16} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
          <Input className="ps-9" placeholder="ابحث..." value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
        </div>
        <div className="mt-3 flex max-h-72 flex-col gap-1 overflow-y-auto">
          {(data?.items || []).map((s) => (
            <button
              key={s.id}
              disabled={existingIds.has(s.id)}
              onClick={() => onAdd(s.id)}
              className="flex items-center justify-between rounded-md px-3 py-2 text-start text-body-sm hover:bg-surface-2 disabled:opacity-40"
            >
              <span>{s.full_name} <span className="text-caption ltr">({s.student_code})</span></span>
              {existingIds.has(s.id) ? <Badge tone="neutral">عضو بالفعل</Badge> : <Plus size={15} />}
            </button>
          ))}
          {q && (data?.items.length || 0) === 0 ? <p className="p-3 text-body-sm text-text-muted">لا نتائج.</p> : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
