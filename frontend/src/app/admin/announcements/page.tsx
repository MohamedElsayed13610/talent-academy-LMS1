"use client";

import { Megaphone, Plus, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useAnnouncements, useCreateAnnouncement, useDeleteAnnouncement, useUpdateAnnouncement } from "@/hooks/use-announcements";
import { useCourses } from "@/hooks/use-courses";
import { useGroups } from "@/hooks/use-groups";
import { ApiError } from "@/lib/api";
import { formatCairo } from "@/lib/cairo-time";
import type { AdminAnnouncementOut, AnnouncementTargetType } from "@/lib/types";

const TARGET_LABEL: Record<AnnouncementTargetType, string> = { all: "كل الطلاب", course: "كورس محدد", group: "مجموعة محددة" };

export default function AdminAnnouncementsPage() {
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<AdminAnnouncementOut | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminAnnouncementOut | null>(null);
  const { data, isLoading, error, refetch } = useAnnouncements(page);
  const deleteAnnouncement = useDeleteAnnouncement();

  return (
    <div className="talent-admin-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-h1">الإعلانات</h1>
          <p className="mt-1 text-body-sm text-text-muted">إعلانات لكل الطلاب، أو لكورس محدد، أو لمجموعة محددة.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}><Plus size={16} /> إعلان جديد</Button>
      </div>

      <div className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الإعلانات"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="flex flex-col gap-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full" />)}</div>
        ) : (data?.items.length || 0) === 0 ? (
          <EmptyState icon={Megaphone} title="لا يوجد إعلانات" description="أضف أول إعلان لطلابك." />
        ) : (
          <div className="flex flex-col gap-2">
            {data?.items.map((a) => (
              <div key={a.id} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface p-4">
                <div className="flex-1 cursor-pointer" onClick={() => setEditTarget(a)}>
                  <div className="flex items-center gap-2">
                    <h3 className="text-h3">{a.title}</h3>
                    <Badge tone={a.is_active ? "success" : "neutral"}>{a.is_active ? "مفعل" : "غير مفعل"}</Badge>
                    <Badge tone="info">{a.target_type === "course" ? a.course_title : a.target_type === "group" ? a.group_name : TARGET_LABEL.all}</Badge>
                  </div>
                  {a.body ? <p className="mt-1 line-clamp-2 text-body-sm text-text-muted">{a.body}</p> : null}
                  <p className="mt-1 text-caption text-text-subtle">{formatCairo(a.created_at)}</p>
                </div>
                <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(a)} aria-label="حذف"><Trash2 size={16} className="text-danger-fg" /></Button>
              </div>
            ))}
          </div>
        )}
        {data ? <div className="mt-3"><Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} /></div> : null}
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <AnnouncementForm onDone={() => setCreateOpen(false)} />
      </Dialog>
      <Dialog open={editTarget !== null} onOpenChange={(open) => !open && setEditTarget(null)}>
        {editTarget ? <AnnouncementForm announcement={editTarget} onDone={() => setEditTarget(null)} /> : null}
      </Dialog>
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`حذف "${deleteTarget?.title}"`}
        destructive
        loading={deleteAnnouncement.isPending}
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            await deleteAnnouncement.mutateAsync(deleteTarget.id);
            toast.success("تم حذف الإعلان");
            setDeleteTarget(null);
          } catch {
            // toast already shown globally
          }
        }}
        description="لا يمكن التراجع عن هذا الإجراء."
      />
    </div>
  );
}

function AnnouncementForm({ announcement, onDone }: { announcement?: AdminAnnouncementOut; onDone: () => void }) {
  const create = useCreateAnnouncement();
  const update = useUpdateAnnouncement(announcement?.id ?? 0);
  const { data: courses } = useCourses();
  const { data: groupsPage } = useGroups();
  const [targetType, setTargetType] = useState<AnnouncementTargetType>(announcement?.target_type || "all");
  const [isActive, setIsActive] = useState(announcement?.is_active ?? true);
  const mutation = announcement ? update : create;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload = {
      title: String(form.get("title") || "").trim(),
      body: String(form.get("body") || "").trim(),
      target_type: targetType,
      course_id: targetType === "course" ? Number(form.get("course_id")) : null,
      group_id: targetType === "group" ? Number(form.get("group_id")) : null,
      is_active: isActive,
    };
    try {
      if (announcement) await update.mutateAsync(payload);
      else await create.mutateAsync(payload);
      toast.success(announcement ? "تم حفظ الإعلان" : "تم إضافة الإعلان");
      onDone();
    } catch {
      // surfaced via mutation.error below
    }
  }

  return (
    <DialogContent side="end">
      <DialogHeader>
        <DialogTitle>{announcement ? "تعديل الإعلان" : "إعلان جديد"}</DialogTitle>
        <DialogDescription>اختر الفئة المستهدفة، ثم اكتب العنوان والنص.</DialogDescription>
      </DialogHeader>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="title">العنوان</Label>
          <Input id="title" name="title" required minLength={2} defaultValue={announcement?.title} autoFocus />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="body">النص</Label>
          <Textarea id="body" name="body" rows={4} defaultValue={announcement?.body} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="target_type">الفئة المستهدفة</Label>
          <select id="target_type" value={targetType} onChange={(e) => setTargetType(e.target.value as AnnouncementTargetType)} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            <option value="all">كل الطلاب</option>
            <option value="course">كورس محدد</option>
            <option value="group">مجموعة محددة</option>
          </select>
        </div>
        {targetType === "course" ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="course_id">الكورس</Label>
            <select id="course_id" name="course_id" required defaultValue={announcement?.course_id ?? ""} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
              <option value="" disabled>اختر كورس</option>
              {(courses || []).map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
          </div>
        ) : null}
        {targetType === "group" ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="group_id">المجموعة</Label>
            <select id="group_id" name="group_id" required defaultValue={announcement?.group_id ?? ""} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
              <option value="" disabled>اختر مجموعة</option>
              {(groupsPage?.items || []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </div>
        ) : null}
        <div className="flex items-center justify-between rounded-md bg-surface-2 px-4 py-3">
          <Label htmlFor="is_active">مفعل</Label>
          <Switch id="is_active" checked={isActive} onCheckedChange={setIsActive} />
        </div>
        {mutation.error ? <p className="text-body-sm text-danger-fg">{(mutation.error as ApiError).message}</p> : null}
        <Button loading={mutation.isPending}>{announcement ? "حفظ" : "إضافة"}</Button>
      </form>
    </DialogContent>
  );
}
