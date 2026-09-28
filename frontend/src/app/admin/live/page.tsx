"use client";

import Link from "next/link";
import { Calendar, ClipboardList, Plus, Radio, Trash2, Video } from "lucide-react";
import { FormEvent, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useCourses } from "@/hooks/use-courses";
import { useGroups } from "@/hooks/use-groups";
import { useCreateLiveSession, useDeleteLiveSession, useLiveSessions, useUpdateLiveSession, type LiveSessionFilters } from "@/hooks/use-live-sessions";
import { ApiError } from "@/lib/api";
import type { AdminLiveSession } from "@/lib/types";

const ALL = "__all__";
const STATUS_LABEL: Record<string, string> = { upcoming: "قادمة", live: "جارية الآن", ended: "انتهت" };

function statusOf(session: AdminLiveSession): "upcoming" | "live" | "ended" {
  const now = Date.now();
  const starts = new Date(session.starts_at).getTime();
  const ends = new Date(session.ends_at).getTime();
  if (now < starts) return "upcoming";
  if (now > ends) return "ended";
  return "live";
}

function toLocalInput(iso?: string) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// Hoisted to module scope (not nested inside AdminLivePage): a component defined inside another
// component's render body gets a new identity every render, so React would remount it — and the
// hooks it calls (useCreateLiveSession/useUpdateLiveSession) would violate the rules of hooks by
// having an inconsistent call history across renders.
function SessionFormContent({ mode, initial, onDone }: { mode: "create" | "edit"; initial?: AdminLiveSession; onDone: () => void }) {
  const { data: courses } = useCourses();
  const { data: groupsPage } = useGroups();
  const createSession = useCreateLiveSession();
  const updateSession = useUpdateLiveSession(initial?.id ?? 0);
  const mutation = mode === "create" ? createSession : updateSession;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const groupValue = String(form.get("group_id") || "");
    const payload = {
      title: String(form.get("title") || "").trim(),
      description: String(form.get("description") || "").trim(),
      course_id: Number(form.get("course_id")),
      group_id: groupValue ? Number(groupValue) : null,
      provider: String(form.get("provider") || "Zoom").trim(),
      join_url: String(form.get("join_url") || "").trim(),
      starts_at: new Date(String(form.get("starts_at"))).toISOString(),
      ends_at: new Date(String(form.get("ends_at"))).toISOString(),
      recording_url: String(form.get("recording_url") || "").trim() || null,
    };
    try {
      await mutation.mutateAsync(payload);
      toast.success(mode === "create" ? "تم إنشاء الحصة" : "تم حفظ التعديلات");
      onDone();
    } catch {
      // surfaced via mutation.error below
    }
  }

  return (
    <DialogContent side="end">
      <DialogHeader>
        <DialogTitle>{mode === "create" ? "إنشاء حصة لايف" : `تعديل ${initial?.title}`}</DialogTitle>
        <DialogDescription>اربط الحصة بكورس، واختياريًا بمجموعة واحدة فقط داخل هذا الكورس.</DialogDescription>
      </DialogHeader>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="title">عنوان الحصة</Label>
          <Input id="title" name="title" required minLength={2} defaultValue={initial?.title} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="course_id">الكورس</Label>
          <select id="course_id" name="course_id" required defaultValue={initial?.course_id || ""} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            <option value="" disabled>اختر كورس</option>
            {(courses || []).map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="group_id">مجموعة محددة (اختياري)</Label>
          <select id="group_id" name="group_id" defaultValue={initial?.group_id || ""} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            <option value="">كل طلاب الكورس</option>
            {(groupsPage?.items || []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="starts_at">وقت البداية</Label>
            <Input id="starts_at" name="starts_at" type="datetime-local" required defaultValue={toLocalInput(initial?.starts_at)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ends_at">وقت النهاية</Label>
            <Input id="ends_at" name="ends_at" type="datetime-local" required defaultValue={toLocalInput(initial?.ends_at)} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="provider">المنصة</Label>
            <Input id="provider" name="provider" defaultValue={initial?.provider || "Zoom"} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="join_url">رابط الدخول</Label>
            <Input id="join_url" name="join_url" dir="ltr" required defaultValue={initial?.join_url} placeholder="https://zoom.us/j/..." />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="recording_url">رابط التسجيل (بعد انتهاء الحصة)</Label>
          <Input id="recording_url" name="recording_url" dir="ltr" defaultValue={initial?.recording_url || ""} placeholder="https://youtube.com/..." />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="description">وصف (اختياري)</Label>
          <Textarea id="description" name="description" rows={2} defaultValue={initial?.description} />
        </div>
        {mutation.error ? <p className="text-body-sm text-danger-fg">{(mutation.error as ApiError).message}</p> : null}
        <Button loading={mutation.isPending}>{mode === "create" ? "إنشاء" : "حفظ"}</Button>
      </form>
    </DialogContent>
  );
}

export default function AdminLivePage() {
  const [filters, setFilters] = useState<LiveSessionFilters>({});
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<AdminLiveSession | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminLiveSession | null>(null);

  const { data: sessions, isLoading, error, refetch } = useLiveSessions(filters);
  const { data: courses } = useCourses();
  const deleteSession = useDeleteLiveSession();

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteSession.mutateAsync(deleteTarget.id);
      toast.success(`تم حذف ${deleteTarget.title}`);
      setDeleteTarget(null);
    } catch {
      // toast already shown globally
    }
  }

  return (
    <div className="talent-admin-page">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-6">
        <div>
          <span className="text-overline text-primary">LIVE SESSIONS</span>
          <h1 className="mt-1 text-h1">الحصص اللايف</h1>
          <p className="mt-1 text-body-sm text-text-muted">أنشئ حصة واربطها بكورس، واختياريًا بمجموعة معينة فقط.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" asChild><Link href="/admin/attendance"><ClipboardList size={17} /> شاشة الحضور</Link></Button>
          <Button onClick={() => setCreateOpen(true)}><Plus size={17} /> إنشاء حصة</Button>
        </div>
      </header>

      <section className="mt-6 flex flex-wrap items-center gap-3">
        <Select value={filters.status || ALL} onValueChange={(v) => setFilters((f) => ({ ...f, status: v === ALL ? undefined : v }))}>
          <SelectTrigger className="w-40"><SelectValue placeholder="الحالة" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الحالات</SelectItem>
            <SelectItem value="upcoming">قادمة</SelectItem>
            <SelectItem value="live">جارية الآن</SelectItem>
            <SelectItem value="ended">انتهت</SelectItem>
          </SelectContent>
        </Select>
        <Select value={filters.course_id ? String(filters.course_id) : ALL} onValueChange={(v) => setFilters((f) => ({ ...f, course_id: v === ALL ? undefined : Number(v) }))}>
          <SelectTrigger className="w-48"><SelectValue placeholder="الكورس" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الكورسات</SelectItem>
            {(courses || []).map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.title}</SelectItem>)}
          </SelectContent>
        </Select>
      </section>

      <section className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الحصص"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="flex flex-col gap-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full" />)}</div>
        ) : (sessions?.length || 0) === 0 ? (
          <EmptyState icon={Radio} title="لا توجد حصص" description="أنشئ أول حصة لايف." action={<Button onClick={() => setCreateOpen(true)}><Plus size={16} /> إنشاء حصة</Button>} />
        ) : (
          <div className="flex flex-col gap-2">
            {sessions?.map((session) => {
              const status = statusOf(session);
              return (
                <div key={session.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-h3">{session.title}</h3>
                      <Badge tone={status === "live" ? "danger" : status === "upcoming" ? "info" : "neutral"}>{STATUS_LABEL[status]}</Badge>
                      {!session.is_active ? <Badge tone="neutral">معطّلة</Badge> : null}
                    </div>
                    <p className="mt-1 flex items-center gap-3 text-caption text-text-muted">
                      <span className="flex items-center gap-1"><Video size={13} /> {session.course_title}{session.group_name ? ` · ${session.group_name}` : ""}</span>
                      <span className="flex items-center gap-1"><Calendar size={13} /> {new Date(session.starts_at).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" })}</span>
                    </p>
                    <p className="mt-1 text-caption text-text-muted">
                      {session.audience_count} طالب · حاضر {session.attendance.present} · متأخر {session.attendance.late} · غائب {session.attendance.absent}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="secondary" size="sm" asChild><Link href={`/admin/attendance/${session.id}`}>الحضور</Link></Button>
                    <Button variant="secondary" size="sm" onClick={() => setEditTarget(session)}>تعديل</Button>
                    <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(session)}><Trash2 size={15} className="text-danger-fg" /></Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <SessionFormContent mode="create" onDone={() => setCreateOpen(false)} />
      </Dialog>

      <Dialog open={!!editTarget} onOpenChange={(open) => !open && setEditTarget(null)}>
        {editTarget ? <SessionFormContent mode="edit" initial={editTarget} onDone={() => setEditTarget(null)} /> : null}
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`حذف ${deleteTarget?.title || ""}`}
        destructive
        loading={deleteSession.isPending}
        onConfirm={handleDelete}
        description="سيتم حذف سجلات الحضور المرتبطة بهذه الحصة. النقاط الممنوحة للطلاب تبقى كما هي."
      />
    </div>
  );
}
