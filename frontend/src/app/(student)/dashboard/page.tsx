"use client";

import Link from "next/link";
import { useState } from "react";
import { Award, BookOpen, CalendarClock, CheckCircle2, Clock, FileQuestion, Medal, MessageCircle, Trophy, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import { CourseCard } from "@/components/course-card";
import { useBranding } from "@/hooks/use-branding";
import { useDashboard } from "@/hooks/use-dashboard";
import { useMe } from "@/hooks/use-auth";
import { useMyLeaderboard } from "@/hooks/use-points";
import { ApiError } from "@/lib/api";
import { formatCairo } from "@/lib/cairo-time";
import type { AccessBlockedReason } from "@/lib/types";

const ACCESS_BLOCKED_MESSAGE: Record<AccessBlockedReason, string> = {
  subscription_expired: "انتهى اشتراكك — تواصل معنا لتجديده والوصول لكل الكورسات.",
  subscription_pending: "اشتراكك قيد المراجعة حاليًا — هيتفعّل قريبًا.",
  subscription_suspended: "تم إيقاف اشتراكك مؤقتًا — تواصل مع الإدارة.",
};

export default function DashboardPage() {
  const { data: me } = useMe();
  const { data: branding } = useBranding();
  const { data, isLoading, error, refetch } = useDashboard();
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  // Defaults to the first enrolled course once the dashboard loads, without an effect: this only
  // tracks an explicit user pick, and always derives the actual selected value from live data.
  const leaderboardCourseId = selectedCourseId ?? data?.courses[0]?.id ?? null;
  const { data: board, isLoading: boardLoading, error: boardError } = useMyLeaderboard(leaderboardCourseId, 10);

  return (
    <div>
      <h1 className="text-h1">أهلاً {me?.full_name.split(" ")[0]} 👋</h1>
      <p className="mt-1 text-body-sm text-text-muted">ملخص يومك الدراسي.</p>

      {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل لوحة التحكم"} onRetry={() => refetch()} /> : null}

      {isLoading ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
      ) : data?.access_blocked ? (
        <div className="mt-6 flex flex-col items-center gap-3 rounded-lg border border-warning-soft bg-warning-soft px-6 py-10 text-center">
          <p className="text-body-lg text-warning-fg">{ACCESS_BLOCKED_MESSAGE[data.access_blocked.reason]}</p>
          {branding?.whatsapp_url ? (
            <a href={branding.whatsapp_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 rounded-md bg-primary px-4 py-2.5 text-body-sm font-medium text-primary-fg hover:bg-primary-hover">
              <MessageCircle size={16} /> تواصل عبر واتساب
            </a>
          ) : null}
        </div>
      ) : data ? (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile icon={Trophy} label="إجمالي النقاط" value={data.points.total} hint={`${data.points.monthly} هذا الشهر`} />
            <StatTile icon={Users} label="نسبة الحضور" value={`${data.attendance.rate}%`} hint={`${data.attendance.present + data.attendance.late} من ${data.attendance.total}`} tone="accent" />
            <StatTile icon={BookOpen} label="الكورسات" value={data.courses.length} />
            <StatTile icon={CheckCircle2} label="إشعارات غير مقروءة" value={data.unread_notifications} tone="accent" />
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            {data.next_session ? (
              <Link href="/live" className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-5 shadow-[var(--shadow-1)] hover:border-border-strong">
                <span className="flex items-center gap-1.5 text-overline text-primary-soft-fg"><CalendarClock size={14} /> أقرب حصة</span>
                <h3 className="text-h3">{data.next_session.title}</h3>
                <p className="text-caption text-text-muted">{data.next_session.course_title}</p>
                <p className="text-body-sm">{formatCairo(data.next_session.starts_at)}</p>
              </Link>
            ) : null}
            {data.next_exam ? (
              <Link href={`/exams/${data.next_exam.id}`} className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-5 shadow-[var(--shadow-1)] hover:border-border-strong">
                <span className="flex items-center gap-1.5 text-overline text-primary-soft-fg"><FileQuestion size={14} /> أقرب امتحان</span>
                <h3 className="text-h3">{data.next_exam.title}</h3>
                <p className="text-caption text-text-muted">{data.next_exam.course_title}</p>
                <p className="flex items-center gap-1.5 text-body-sm"><Clock size={14} /> {data.next_exam.duration} دقيقة</p>
              </Link>
            ) : null}
          </div>

          {data.course_ranks.length === 0 ? null : (
            <div className="mt-6 rounded-lg border border-border bg-surface p-5">
              <h3 className="text-h3">ترتيبك في الكورسات</h3>
              <div className="mt-3 flex flex-col gap-2">
                {data.course_ranks.map((c) => (
                  <div key={c.course_id} className="flex items-center justify-between rounded-md bg-surface-2 px-4 py-2.5 text-body-sm">
                    <span>{c.course_title}</span>
                    <span className="flex items-center gap-2">
                      <Badge tone="primary">#{c.rank}</Badge>
                      <span className="text-text-muted">{c.points} نقطة</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.courses.length > 0 ? (
            <div className="mt-6 rounded-lg border border-border bg-surface p-5">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-h3">زملاؤك في الكورس</h3>
                <div className="w-full sm:w-56">
                  <Select value={leaderboardCourseId ? String(leaderboardCourseId) : undefined} onValueChange={(v) => setSelectedCourseId(Number(v))}>
                    <SelectTrigger><SelectValue placeholder="اختر كورس" /></SelectTrigger>
                    <SelectContent>
                      {data.courses.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.title}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {boardError ? (
                <ErrorState message={boardError instanceof ApiError ? boardError.message : "تعذر تحميل ترتيب الكورس"} />
              ) : boardLoading ? (
                <Skeleton className="h-48 w-full" />
              ) : !board || board.rows.length === 0 ? (
                <EmptyState icon={Medal} title="لا يوجد طلاب بعد" description="ترتيب الزملاء في هذا الكورس هيظهر لما يبدأوا كسب نقاط." />
              ) : (
                <div className="overflow-hidden rounded-lg border border-border">
                  {board.rows.map((row) => (
                    <div
                      key={row.student_id}
                      className={`flex items-center justify-between gap-3 border-b border-border px-4 py-2.5 text-body-sm last:border-b-0 ${row.is_me ? "bg-primary-soft" : ""}`}
                    >
                      <div className="flex items-center gap-3">
                        <span className={`flex size-7 items-center justify-center rounded-full text-caption font-bold ${row.rank <= 3 ? "bg-accent-soft text-accent-fg" : "bg-surface-2 text-text-muted"}`}>
                          {row.rank}
                        </span>
                        <span className={row.is_me ? "font-semibold" : ""}>{row.display_name}{row.is_me ? " (أنت)" : ""}</span>
                      </div>
                      <Badge tone={row.is_me ? "primary" : "neutral"}>{row.points} نقطة</Badge>
                    </div>
                  ))}
                  {board.me && !board.rows.some((r) => r.is_me) ? (
                    <div className="flex items-center justify-between gap-3 border-t-2 border-primary bg-primary-soft px-4 py-2.5 text-body-sm">
                      <div className="flex items-center gap-3">
                        <span className="flex size-7 items-center justify-center rounded-full bg-surface-2 text-caption font-bold text-text-muted">{board.me.rank}</span>
                        <span className="font-semibold">{board.me.display_name} (أنت)</span>
                      </div>
                      <Badge tone="primary">{board.me.points} نقطة</Badge>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          ) : null}

          {data.recent_results.length > 0 ? (
            <div className="mt-6 rounded-lg border border-border bg-surface p-5">
              <h3 className="text-h3">آخر النتائج</h3>
              <div className="mt-3 flex flex-col gap-2">
                {data.recent_results.map((r) => (
                  <div key={r.attempt_id} className="flex items-center justify-between rounded-md bg-surface-2 px-4 py-2.5 text-body-sm">
                    <span>{r.exam_title}</span>
                    <span className="flex items-center gap-2">
                      <Badge tone={r.passed ? "success" : "danger"}>{r.percentage}%</Badge>
                      <span className="text-text-subtle">{r.submitted_at ? formatCairo(r.submitted_at) : ""}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="mt-6">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-h3">كورساتك</h3>
              <Link href="/courses" className="text-body-sm text-primary hover:underline">عرض الكل</Link>
            </div>
            {data.courses.length === 0 ? (
              <EmptyState icon={BookOpen} title="لسه مفيش كورسات متاحة" description="أي كورس يضيفه الأدمن لحسابك هيظهر هنا." />
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {data.courses.slice(0, 3).map((course) => <CourseCard key={course.id} course={course} />)}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
