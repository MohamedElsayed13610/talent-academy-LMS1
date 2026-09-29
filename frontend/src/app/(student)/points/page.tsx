"use client";

import { Award, Medal, Trophy } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Pagination } from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import { useMyCourses } from "@/hooks/use-my-courses";
import { useMyLeaderboard, useMyPoints } from "@/hooks/use-points";
import { ApiError } from "@/lib/api";
import { formatCairo } from "@/lib/cairo-time";

export default function PointsPage() {
  const { data: courses } = useMyCourses();
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  // Defaults to the first course once courses load, without an effect: courseId only tracks an
  // explicit user pick, and this derives the actual value shown/queried on every render.
  const courseId = selectedCourseId ?? courses?.[0]?.id ?? null;

  const { data: points, isLoading: pointsLoading, error: pointsError, refetch: refetchPoints } = useMyPoints(historyPage);
  const { data: board, isLoading: boardLoading, error: boardError } = useMyLeaderboard(courseId);

  return (
    <div>
      <h1 className="text-h1">النقاط والترتيب</h1>
      <p className="mt-1 text-body-sm text-text-muted">نقاطك وترتيبك بين زملائك في كل كورس.</p>

      {pointsError ? <ErrorState message={pointsError instanceof ApiError ? pointsError.message : "تعذر تحميل النقاط"} onRetry={() => refetchPoints()} /> : null}

      {pointsLoading ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">{[1, 2].map((i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
      ) : points ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <StatTile icon={Trophy} label="إجمالي النقاط" value={points.total} />
          <StatTile icon={Award} label="هذا الشهر" value={points.monthly} tone="accent" />
        </div>
      ) : null}

      <div className="mt-8">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-h3">لوحة الصدارة</h3>
          <div className="w-56">
            <Select value={courseId ? String(courseId) : undefined} onValueChange={(v) => setSelectedCourseId(Number(v))}>
              <SelectTrigger><SelectValue placeholder="اختر كورس" /></SelectTrigger>
              <SelectContent>
                {(courses || []).map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.title}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        {boardError ? <ErrorState message={boardError instanceof ApiError ? boardError.message : "تعذر تحميل لوحة الصدارة"} /> : null}
        {boardLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : !board ? (
          <EmptyState icon={Medal} title="اختر كورس" description="اختر كورس من القائمة لعرض لوحة الصدارة." />
        ) : board.rows.length === 0 ? (
          <EmptyState icon={Medal} title="لا يوجد طلاب بعد" description="لوحة الصدارة هتظهر لما يبدأ الطلاب في كسب نقاط." />
        ) : (
          <div className="overflow-hidden rounded-lg border border-border">
            {board.rows.map((row) => (
              <div
                key={row.student_id}
                className={`flex items-center justify-between gap-3 border-b border-border px-4 py-3 text-body-sm last:border-b-0 ${row.is_me ? "bg-primary-soft" : ""}`}
              >
                <div className="flex items-center gap-3">
                  <span className={`flex size-8 items-center justify-center rounded-full text-caption font-bold ${row.rank <= 3 ? "bg-accent-soft text-accent-fg" : "bg-surface-2 text-text-muted"}`}>
                    {row.rank}
                  </span>
                  <span className={row.is_me ? "font-semibold" : ""}>{row.display_name}{row.is_me ? " (أنت)" : ""}</span>
                </div>
                <Badge tone={row.is_me ? "primary" : "neutral"}>{row.points} نقطة</Badge>
              </div>
            ))}
            {board.me && !board.rows.some((r) => r.is_me) ? (
              <div className="flex items-center justify-between gap-3 border-t-2 border-primary bg-primary-soft px-4 py-3 text-body-sm">
                <div className="flex items-center gap-3">
                  <span className="flex size-8 items-center justify-center rounded-full bg-surface-2 text-caption font-bold text-text-muted">{board.me.rank}</span>
                  <span className="font-semibold">{board.me.display_name} (أنت)</span>
                </div>
                <Badge tone="primary">{board.me.points} نقطة</Badge>
              </div>
            ) : null}
          </div>
        )}
      </div>

      <div className="mt-8">
        <h3 className="mb-3 text-h3">سجل النقاط</h3>
        {points && points.history.length === 0 ? (
          <EmptyState icon={Award} title="لا يوجد نقاط بعد" description="أي نقاط تكسبها هتظهر هنا." />
        ) : (
          <div className="flex flex-col gap-2">
            {points?.history.map((event) => (
              <div key={event.id} className="flex items-center justify-between gap-3 rounded-md border border-border px-4 py-2.5 text-body-sm">
                <div>
                  <div>{event.description}</div>
                  <div className="text-caption text-text-subtle">{event.course_title ? `${event.course_title} · ` : ""}{formatCairo(event.created_at)}</div>
                </div>
                <Badge tone={event.points >= 0 ? "success" : "danger"}>{event.points >= 0 ? "+" : ""}{event.points}</Badge>
              </div>
            ))}
          </div>
        )}
        {points ? <div className="mt-3"><Pagination page={points.page} pageSize={points.page_size} total={points.history_total} onPageChange={setHistoryPage} /></div> : null}
      </div>
    </div>
  );
}
