"use client";

import Link from "next/link";
import { Calendar, ClipboardList } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useLiveSessions } from "@/hooks/use-live-sessions";
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

export default function AttendancePickerPage() {
  const [status, setStatus] = useState<string | undefined>(undefined);
  const { data: sessions, isLoading, error, refetch } = useLiveSessions({ status });

  return (
    <div className="talent-admin-page">
      <header className="border-b border-border pb-6">
        <span className="text-overline text-primary">ATTENDANCE</span>
        <h1 className="mt-1 text-h1">الحضور</h1>
        <p className="mt-1 text-body-sm text-text-muted">اختر حصة لفتح شاشة تسجيل الحضور السريعة.</p>
      </header>

      <div className="mt-6 max-w-xs">
        <Select value={status || ALL} onValueChange={(v) => setStatus(v === ALL ? undefined : v)}>
          <SelectTrigger><SelectValue placeholder="الحالة" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>كل الحالات</SelectItem>
            <SelectItem value="live">جارية الآن</SelectItem>
            <SelectItem value="upcoming">قادمة</SelectItem>
            <SelectItem value="ended">انتهت</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <section className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الحصص"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="flex flex-col gap-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16 w-full" />)}</div>
        ) : (sessions?.length || 0) === 0 ? (
          <EmptyState icon={ClipboardList} title="لا توجد حصص" description="أنشئ حصة لايف أولًا من صفحة الحصص." />
        ) : (
          <div className="flex flex-col gap-2">
            {sessions?.map((session) => {
              const sessionStatus = statusOf(session);
              return (
                <Link key={session.id} href={`/admin/attendance/${session.id}`} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4 hover:shadow-[var(--shadow-1)]">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-h3">{session.title}</h3>
                      <Badge tone={sessionStatus === "live" ? "danger" : sessionStatus === "upcoming" ? "info" : "neutral"}>{STATUS_LABEL[sessionStatus]}</Badge>
                    </div>
                    <p className="mt-1 flex items-center gap-2 text-caption text-text-muted">
                      <span>{session.course_title}{session.group_name ? ` · ${session.group_name}` : ""}</span>
                      <span className="flex items-center gap-1"><Calendar size={13} /> {new Date(session.starts_at).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" })}</span>
                    </p>
                  </div>
                  <span className="text-caption text-text-muted">
                    {session.attendance.present + session.attendance.late}/{session.audience_count} مسجّل
                  </span>
                </Link>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
