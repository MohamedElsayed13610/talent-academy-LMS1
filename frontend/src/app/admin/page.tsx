"use client";

import Link from "next/link";
import { AlertTriangle, BookOpen, CalendarClock, CheckCircle2, FileQuestion, Info, Layers, ListChecks, Trophy, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import { useAdminDashboard } from "@/hooks/use-admin-dashboard";
import { useMe } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { formatCairo } from "@/lib/cairo-time";
import type { AdminWarningSeverity } from "@/lib/types";

const WARNING_TONE: Record<AdminWarningSeverity, "danger" | "warning" | "info"> = {
  danger: "danger", warning: "warning", info: "info",
};

const SUBSCRIPTION_LABELS: Record<string, string> = {
  active: "نشط", pending: "قيد المراجعة", expired: "منتهي", suspended: "موقوف",
};

export default function AdminOverviewPage() {
  const { data: me, isLoading: meLoading } = useMe();
  const { data, isLoading, error, refetch } = useAdminDashboard();

  return (
    <div>
      {meLoading ? <Skeleton className="h-9 w-72" /> : <h1 className="text-h1">مرحبًا {me?.full_name} — نظرة عامة</h1>}
      <p className="mt-2 text-body-sm text-text-muted">ملخص حي لحالة الأكاديمية الآن.</p>

      {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الإحصائيات"} onRetry={() => refetch()} /> : null}

      {isLoading ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[1, 2, 3, 4, 5, 6, 7, 8].map((i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
      ) : !data ? null : (
        <>
          {data.warnings.length > 0 ? (
            <div className="mt-6 flex flex-col gap-2">
              {data.warnings.map((w) => (
                <div key={w.code} className="flex items-center gap-2.5 rounded-lg border border-border bg-surface px-4 py-3 text-body-sm">
                  {w.severity === "danger" ? <AlertTriangle size={17} className="shrink-0 text-danger-fg" /> : <Info size={17} className="shrink-0 text-warning-fg" />}
                  <span className="flex-1">{w.message}</span>
                  {w.count !== null ? <Badge tone={WARNING_TONE[w.severity]}>{w.count}</Badge> : null}
                </div>
              ))}
            </div>
          ) : null}

          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile icon={Users} label="إجمالي الطلاب" value={data.students.total} hint={`${data.students.active} نشط`} />
            <StatTile icon={BookOpen} label="الكورسات" value={data.courses.total} hint={`${data.courses.published} منشور`} tone="accent" />
            <StatTile icon={Layers} label="المجموعات" value={data.groups.total} />
            <StatTile icon={Trophy} label="نقاط ممنوحة" value={data.total_points_awarded} tone="accent" />
            <StatTile icon={CalendarClock} label="حصص قادمة (٧ أيام)" value={data.sessions.upcoming_7d} hint={data.sessions.live_now > 0 ? `${data.sessions.live_now} مباشرة الآن` : undefined} />
            <StatTile icon={FileQuestion} label="امتحانات مفتوحة الآن" value={data.exams.open_now} hint={`${data.exams.upcoming_7d} قادمة`} tone="accent" />
            <StatTile icon={CheckCircle2} label="نسبة الحضور (٣٠ يوم)" value={`${data.attendance.rate_30d}%`} hint={`${data.attendance.records_30d} سجل`} />
            <StatTile icon={ListChecks} label="حصص محتاجة اعتماد الحضور" value={data.sessions.pending_finalization} tone="accent" />
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>الاشتراكات</CardTitle></CardHeader>
              <div className="flex flex-col gap-2">
                {Object.entries(data.students.by_subscription).map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between rounded-md bg-surface-2 px-3.5 py-2.5 text-body-sm">
                    <span>{SUBSCRIPTION_LABELS[status] || status}</span>
                    <Badge tone={status === "active" ? "success" : status === "expired" ? "danger" : "neutral"}>{count}</Badge>
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <CardHeader><CardTitle>أقرب حصة</CardTitle></CardHeader>
              {data.sessions.next ? (
                <Link href="/admin/live" className="flex flex-col gap-1 rounded-md bg-surface-2 px-3.5 py-3 text-body-sm hover:border hover:border-border-strong">
                  <span className="font-medium">{data.sessions.next.title}</span>
                  <span className="text-text-muted">{data.sessions.next.course_title}</span>
                  <span className="text-caption text-text-subtle">{formatCairo(data.sessions.next.starts_at)}</span>
                </Link>
              ) : (
                <p className="text-body-sm text-text-muted">لا يوجد حصص قادمة.</p>
              )}
            </Card>
          </div>

          <div className="mt-6">
            <h3 className="mb-3 text-h3">آخر النشاطات</h3>
            {data.recent_activity.length === 0 ? (
              <EmptyState icon={ListChecks} title="لا يوجد نشاط بعد" description="أي إجراء إداري هيظهر هنا." />
            ) : (
              <div className="overflow-hidden rounded-lg border border-border">
                {data.recent_activity.map((a) => (
                  <div key={a.id} className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 text-body-sm last:border-b-0">
                    <div>
                      <span className="font-medium">{a.actor_label || "النظام"}</span>
                      <span className="text-text-muted"> — {a.action}</span>
                    </div>
                    <span className="text-caption text-text-subtle">{formatCairo(a.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
