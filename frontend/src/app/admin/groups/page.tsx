"use client";

import Link from "next/link";
import { AlertTriangle, BookOpen, Plus, Search, Trash2, UsersRound } from "lucide-react";
import { FormEvent, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCreateGroup, useDeleteGroup, useGroups } from "@/hooks/use-groups";
import { ApiError } from "@/lib/api";
import type { AdminGroup } from "@/lib/types";

export default function AdminGroupsPage() {
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<AdminGroup | null>(null);
  const [inUseInfo, setInUseInfo] = useState<{ live_sessions: string[]; exams: string[] } | null>(null);

  const { data, isLoading, error, refetch } = useGroups(q);
  const createGroup = useCreateGroup();
  const deleteGroup = useDeleteGroup();

  async function handleCreate(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await createGroup.mutateAsync({ name: String(form.get("name") || "").trim(), description: String(form.get("description") || "").trim() });
      setCreateOpen(false);
      toast.success("تم إنشاء المجموعة");
    } catch {
      // surfaced via createGroup.error below
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteGroup.mutateAsync(deleteTarget.id);
      toast.success(`تم حذف ${deleteTarget.name}`);
      setDeleteTarget(null);
    } catch (err) {
      if (err instanceof ApiError && err.code === "GROUP_IN_USE") {
        setInUseInfo(err.details as { live_sessions: string[]; exams: string[] });
        setDeleteTarget(null);
      }
    }
  }

  return (
    <div className="talent-admin-page">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-6">
        <div>
          <span className="text-overline text-primary">GROUPS</span>
          <h1 className="mt-1 text-h1">مجموعات الطلاب</h1>
          <p className="mt-1 text-body-sm text-text-muted">مجموعات مخصصة يديرها الأدمن يدويًا — بدون ربط تلقائي بالصف الدراسي.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}><Plus size={17} /> إنشاء مجموعة</Button>
      </header>

      <div className="relative mt-6 max-w-sm">
        <Search size={16} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
        <Input className="ps-9" placeholder="ابحث عن مجموعة..." value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      <section className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل المجموعات"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-32 w-full" />)}</div>
        ) : (data?.items.length || 0) === 0 ? (
          <EmptyState icon={UsersRound} title="لسه مفيش مجموعات" description="أنشئ مجموعة وابدأ بإضافة الطلاب لها." action={<Button onClick={() => setCreateOpen(true)}><Plus size={16} /> إنشاء مجموعة</Button>} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data?.items.map((group) => (
              <Link key={group.id} href={`/admin/groups/${group.id}`} className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-5 transition-shadow hover:shadow-[var(--shadow-2)]">
                <div className="flex items-start justify-between">
                  <h3 className="text-h3">{group.name}</h3>
                  <button
                    onClick={(e) => { e.preventDefault(); setDeleteTarget(group); }}
                    className="text-text-subtle hover:text-danger-fg"
                    aria-label="حذف"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
                {group.description ? <p className="text-body-sm text-text-muted">{group.description}</p> : null}
                <div className="mt-auto flex items-center gap-3 text-caption">
                  <span className="flex items-center gap-1"><UsersRound size={14} /> {group.members_count} طالب</span>
                  <span className="flex items-center gap-1"><BookOpen size={14} /> {group.courses.length} كورس</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>إنشاء مجموعة</DialogTitle>
            <DialogDescription>اسم مميز — مش هيتكرر مع مجموعة تانية.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleCreate} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="name">اسم المجموعة</Label>
              <Input id="name" name="name" required minLength={2} placeholder="مثال: SAT Saturday Group" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="description">وصف المجموعة (اختياري)</Label>
              <Textarea id="description" name="description" rows={2} />
            </div>
            {createGroup.error ? <p className="text-body-sm text-danger-fg">{(createGroup.error as ApiError).message}</p> : null}
            <Button loading={createGroup.isPending}>إنشاء</Button>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`حذف ${deleteTarget?.name || ""}`}
        destructive
        loading={deleteGroup.isPending}
        onConfirm={handleDelete}
        description="سيتم حذف عضويات الطلاب وإسنادات الكورسات لهذه المجموعة فقط — الطلاب أنفسهم يبقون كما هم."
      />

      <Dialog open={!!inUseInfo} onOpenChange={(open) => !open && setInUseInfo(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-danger-fg"><AlertTriangle size={19} /> لا يمكن حذف المجموعة</DialogTitle>
            <DialogDescription>المجموعة مخصصة لحصص أو امتحانات. أعد توجيهها أو احذفها أولًا.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2 text-body-sm">
            {inUseInfo?.live_sessions.map((s) => <span key={s} className="rounded-md bg-surface-2 px-3 py-2">حصة: {s}</span>)}
            {inUseInfo?.exams.map((s) => <span key={s} className="rounded-md bg-surface-2 px-3 py-2">امتحان: {s}</span>)}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
