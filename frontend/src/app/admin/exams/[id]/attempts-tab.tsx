"use client";

import { AlertTriangle, CheckCircle2, Clock, Lock, RotateCw, Unlock } from "lucide-react";
import { FormEvent, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { useAttemptDetail, useExamAttempts, useGrantExtraTime, useGrantNewAttempt, useUnlockAttempt } from "@/hooks/use-admin-attempts";
import { ApiError } from "@/lib/api";
import { formatCairo } from "@/lib/cairo-time";
import type { AdminAttemptDetail, AdminExamDetail, AttemptStatus } from "@/lib/types";

const STATUS_LABEL: Record<AttemptStatus, string> = {
  granted: "منحة إدارية", in_progress: "جارية", locked: "مقفلة", submitted: "تم التسليم", expired: "منتهية", superseded: "مستبدلة",
};
const STATUS_TONE: Record<AttemptStatus, "neutral" | "info" | "success" | "danger" | "primary" | "warning"> = {
  granted: "info", in_progress: "primary", locked: "danger", submitted: "success", expired: "neutral", superseded: "neutral",
};
const STATUS_OPTIONS: AttemptStatus[] = ["granted", "in_progress", "locked", "submitted", "expired", "superseded"];

export function AttemptsTab({ exam }: { exam: AdminExamDetail }) {
  const [status, setStatus] = useState<string>("");
  const [page, setPage] = useState(1);
  const [openAttemptId, setOpenAttemptId] = useState<number | null>(null);
  const { data, isLoading, error, refetch } = useExamAttempts(exam.id, status || null, page);

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-body-sm text-text-muted">كل محاولات الطلاب في هذا الامتحان، مع إجراءات الفتح وإضافة الوقت ومنح محاولة جديدة.</p>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="h-10 rounded-md border border-border bg-surface px-3 text-body-sm"
        >
          <option value="">كل الحالات</option>
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
      </div>

      <div className="mt-4">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل المحاولات"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="flex flex-col gap-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
        ) : (data?.items.length || 0) === 0 ? (
          <EmptyState icon={Clock} title="لا يوجد محاولات" description="لسه محدش بدأ هذا الامتحان." />
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-body-sm">
              <thead className="bg-surface-2 text-caption text-text-muted">
                <tr>
                  <th className="p-3 text-start">الطالب</th>
                  <th className="p-3 text-start">المحاولة</th>
                  <th className="p-3 text-start">الحالة</th>
                  <th className="p-3 text-start">المخالفات</th>
                  <th className="p-3 text-start">الإجابات</th>
                  <th className="p-3 text-start">الدرجة</th>
                  <th className="p-3 text-start">بدأت</th>
                </tr>
              </thead>
              <tbody>
                {data?.items.map((row) => (
                  <tr key={row.attempt_id} className="cursor-pointer border-t border-border hover:bg-surface-2" onClick={() => setOpenAttemptId(row.attempt_id)}>
                    <td className="p-3">
                      <div className="font-medium">{row.student.full_name}</div>
                      <div className="text-caption text-text-subtle">{row.student.student_code}</div>
                    </td>
                    <td className="p-3">#{row.attempt_no}</td>
                    <td className="p-3"><Badge tone={STATUS_TONE[row.status]}>{STATUS_LABEL[row.status]}</Badge></td>
                    <td className="p-3">{row.violation_count > 0 ? <span className="flex items-center gap-1 text-warning-fg"><AlertTriangle size={13} /> {row.violation_count}</span> : "—"}</td>
                    <td className="p-3">{row.answered_count}/{row.question_count}</td>
                    <td className="p-3">{row.percentage !== null ? `${row.percentage}%` : "—"}</td>
                    <td className="p-3 text-caption text-text-subtle">{formatCairo(row.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data ? <div className="mt-3"><Pagination page={page} pageSize={data.page_size} total={data.total} onPageChange={setPage} /></div> : null}
      </div>

      <Dialog open={openAttemptId !== null} onOpenChange={(open) => !open && setOpenAttemptId(null)}>
        {openAttemptId !== null ? <AttemptDetailDialog attemptId={openAttemptId} /> : null}
      </Dialog>
    </div>
  );
}

function AttemptDetailDialog({ attemptId }: { attemptId: number }) {
  const { data: attempt, isLoading, error } = useAttemptDetail(attemptId);
  const [actionOpen, setActionOpen] = useState<"unlock" | "extra-time" | "new-attempt" | null>(null);

  if (isLoading || !attempt) {
    return (
      <DialogContent>
        <DialogHeader><DialogTitle>تفاصيل المحاولة</DialogTitle></DialogHeader>
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل المحاولة"} /> : <Skeleton className="h-64 w-full" />}
      </DialogContent>
    );
  }

  const canUnlock = attempt.status === "locked";
  const canExtraTime = attempt.status === "in_progress" || attempt.status === "locked";
  const canNewAttempt = attempt.status === "in_progress" || attempt.status === "locked" || attempt.status === "submitted" || attempt.status === "expired";

  return (
    <DialogContent className="max-w-2xl">
      <DialogHeader>
        <DialogTitle>{attempt.student.full_name} — محاولة #{attempt.attempt_no}</DialogTitle>
        <DialogDescription>{attempt.student.student_code} · {STATUS_LABEL[attempt.status]}</DialogDescription>
      </DialogHeader>

      <div className="flex max-h-[70vh] flex-col gap-5 overflow-y-auto">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="الدرجة" value={`${attempt.percentage}% (${attempt.score_points}/${attempt.total_points})`} />
          <Stat label="المخالفات" value={`${attempt.violation_count}/${attempt.violation_limit}`} />
          <Stat label="وقت إضافي" value={`${attempt.extra_minutes} دقيقة`} />
          <Stat label="بدأت" value={formatCairo(attempt.started_at)} />
        </div>

        {attempt.lock_reason ? (
          <div className="flex items-center gap-2 rounded-md bg-danger-soft px-4 py-2.5 text-body-sm text-danger-fg">
            <Lock size={15} /> سبب القفل: {attempt.lock_reason}
          </div>
        ) : null}
        {attempt.granted_reason ? (
          <div className="flex items-center gap-2 rounded-md bg-info-soft px-4 py-2.5 text-body-sm text-info-fg">
            <RotateCw size={15} /> سبب المنح: {attempt.granted_reason}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" disabled={!canUnlock} onClick={() => setActionOpen("unlock")}><Unlock size={14} /> فتح القفل</Button>
          <Button size="sm" variant="secondary" disabled={!canExtraTime} onClick={() => setActionOpen("extra-time")}><Clock size={14} /> إضافة وقت</Button>
          <Button size="sm" variant="secondary" disabled={!canNewAttempt} onClick={() => setActionOpen("new-attempt")}><RotateCw size={14} /> منح محاولة جديدة</Button>
        </div>

        <section>
          <h4 className="text-label text-text-muted">الإجابات</h4>
          <div className="mt-2 flex flex-col gap-1.5">
            {attempt.answers.map((a) => (
              <div key={a.question_id} className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-body-sm">
                <span className="flex-1 truncate">سؤال {a.position}: {a.prompt_text || "(صورة)"}</span>
                <span className={`flex items-center gap-1 ${a.is_correct ? "text-success-fg" : a.choice_label ? "text-danger-fg" : "text-text-subtle"}`}>
                  {a.is_correct ? <CheckCircle2 size={14} /> : null}
                  {a.choice_label || "لم يُجب"} {a.correct_label && a.choice_label !== a.correct_label ? `(الصحيح: ${a.correct_label})` : ""}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h4 className="text-label text-text-muted">سجل الأحداث</h4>
          <div className="mt-2 flex flex-col gap-1.5">
            {attempt.events.map((e) => (
              <div key={e.id} className="flex items-center justify-between gap-2 text-caption text-text-muted">
                <span>{EVENT_LABEL[e.event_type] || e.event_type}{e.detail ? ` — ${e.detail}` : ""}{e.actor_name ? ` (${e.actor_name})` : ""}</span>
                <span className="shrink-0">{formatCairo(e.created_at)}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <Dialog open={actionOpen !== null} onOpenChange={(open) => !open && setActionOpen(null)}>
        {actionOpen === "unlock" ? <UnlockForm attempt={attempt} onDone={() => setActionOpen(null)} /> : null}
        {actionOpen === "extra-time" ? <ExtraTimeForm attempt={attempt} onDone={() => setActionOpen(null)} /> : null}
        {actionOpen === "new-attempt" ? <NewAttemptForm attempt={attempt} onDone={() => setActionOpen(null)} /> : null}
      </Dialog>
    </DialogContent>
  );
}

const EVENT_LABEL: Record<string, string> = {
  started: "بدأ المحاولة", resumed: "استأنف المحاولة", violation: "مخالفة", locked: "تم القفل",
  unlocked: "تم فتح القفل", extra_time: "إضافة وقت", new_attempt: "منح محاولة جديدة", superseded: "تم الاستبدال",
  submitted: "تم التسليم", expired: "انتهى الوقت",
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-surface-2 px-3 py-2 text-center">
      <div className="text-body-sm font-semibold">{value}</div>
      <div className="text-caption text-text-subtle">{label}</div>
    </div>
  );
}

function UnlockForm({ attempt, onDone }: { attempt: AdminAttemptDetail; onDone: () => void }) {
  const unlock = useUnlockAttempt(attempt.attempt_id);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await unlock.mutateAsync({ reason: String(form.get("reason") || "").trim(), extra_minutes: Number(form.get("extra_minutes") || 0) });
      toast.success("تم فتح قفل المحاولة");
      onDone();
    } catch {
      // surfaced via unlock.error below
    }
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>فتح قفل المحاولة</DialogTitle>
        <DialogDescription>سيتم تصفير عدد المخالفات، وإذا كان الوقت قد انتهى سيُمنح الطالب وقتًا جديدًا للمتابعة.</DialogDescription>
      </DialogHeader>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reason">السبب</Label>
          <Textarea id="reason" name="reason" required minLength={1} rows={3} autoFocus />
        </div>
        <div className="flex flex-col gap-1.5 max-w-[200px]">
          <Label htmlFor="extra_minutes">دقائق إضافية (اختياري)</Label>
          <Input id="extra_minutes" name="extra_minutes" type="number" min={0} max={360} defaultValue={0} />
        </div>
        {unlock.error ? <p className="text-body-sm text-danger-fg">{(unlock.error as ApiError).message}</p> : null}
        <Button loading={unlock.isPending}>فتح القفل</Button>
      </form>
    </DialogContent>
  );
}

function ExtraTimeForm({ attempt, onDone }: { attempt: AdminAttemptDetail; onDone: () => void }) {
  const grantExtraTime = useGrantExtraTime(attempt.attempt_id);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await grantExtraTime.mutateAsync({ reason: String(form.get("reason") || "").trim(), minutes: Number(form.get("minutes") || 0) });
      toast.success("تم إضافة الوقت");
      onDone();
    } catch {
      // surfaced via grantExtraTime.error below
    }
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>إضافة وقت للمحاولة</DialogTitle>
        <DialogDescription>يُضاف الوقت للموعد الحالي (أو من الآن إذا كان قد انتهى بالفعل).</DialogDescription>
      </DialogHeader>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reason">السبب</Label>
          <Textarea id="reason" name="reason" required minLength={1} rows={3} autoFocus />
        </div>
        <div className="flex flex-col gap-1.5 max-w-[200px]">
          <Label htmlFor="minutes">الدقائق</Label>
          <Input id="minutes" name="minutes" type="number" min={1} max={360} required defaultValue={10} />
        </div>
        {grantExtraTime.error ? <p className="text-body-sm text-danger-fg">{(grantExtraTime.error as ApiError).message}</p> : null}
        <Button loading={grantExtraTime.isPending}>إضافة الوقت</Button>
      </form>
    </DialogContent>
  );
}

function NewAttemptForm({ attempt, onDone }: { attempt: AdminAttemptDetail; onDone: () => void }) {
  const grantNewAttempt = useGrantNewAttempt(attempt.attempt_id);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await grantNewAttempt.mutateAsync({ reason: String(form.get("reason") || "").trim(), extra_minutes: Number(form.get("extra_minutes") || 0) });
      toast.success("تم منح محاولة جديدة");
      onDone();
    } catch {
      // surfaced via grantNewAttempt.error below
    }
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>منح محاولة جديدة</DialogTitle>
        <DialogDescription>
          {attempt.status === "in_progress" || attempt.status === "locked"
            ? "سيتم استبدال هذه المحاولة بمحاولة جديدة تتجاوز حد المحاولات ووقت الامتحان — يبدأ عدها التنازلي عندما يضغط الطالب «بدء»."
            : "ستُمنح محاولة جديدة تتجاوز حد المحاولات ووقت الامتحان، وهذه المحاولة الحالية تبقى كما هي في السجل."}
        </DialogDescription>
      </DialogHeader>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reason">السبب</Label>
          <Textarea id="reason" name="reason" required minLength={1} rows={3} autoFocus />
        </div>
        <div className="flex flex-col gap-1.5 max-w-[200px]">
          <Label htmlFor="extra_minutes">دقائق إضافية (اختياري)</Label>
          <Input id="extra_minutes" name="extra_minutes" type="number" min={0} max={360} defaultValue={0} />
        </div>
        {grantNewAttempt.error ? <p className="text-body-sm text-danger-fg">{(grantNewAttempt.error as ApiError).message}</p> : null}
        <Button loading={grantNewAttempt.isPending}>منح المحاولة</Button>
      </form>
    </DialogContent>
  );
}
