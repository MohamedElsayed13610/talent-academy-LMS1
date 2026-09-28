"use client";

import { Calendar, ExternalLink, PlayCircle, Radio } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useJoinLiveSession, useMyLiveSessions } from "@/hooks/use-my-live-sessions";
import { ApiError } from "@/lib/api";
import type { LiveSessionCard, LiveSessionStatusFilter } from "@/lib/types";

const TABS: { value: LiveSessionStatusFilter; label: string }[] = [
  { value: "upcoming", label: "القادمة" },
  { value: "live", label: "جارية الآن" },
  { value: "ended", label: "انتهت" },
];

export default function StudentLivePage() {
  const [tab, setTab] = useState<LiveSessionStatusFilter>("upcoming");
  const { data: sessions, isLoading, error, refetch } = useMyLiveSessions(tab);
  const join = useJoinLiveSession();
  const [joiningId, setJoiningId] = useState<number | null>(null);

  async function handleJoin(session: LiveSessionCard) {
    setJoiningId(session.id);
    try {
      const result = await join.mutateAsync(session.id);
      // Same-tab navigation right after recording attendance (spec Q3/A19) — not a new tab.
      window.location.assign(result.join_url);
    } catch (err) {
      if (err instanceof ApiError && err.code === "JOIN_NOT_OPEN") toast.error("باب الدخول للحصة لسه ما فتحش");
      else if (err instanceof ApiError && err.code === "SESSION_ENDED") toast.error("انتهت هذه الحصة");
      // any other error already shown globally
    } finally {
      setJoiningId(null);
    }
  }

  return (
    <div>
      <h1 className="text-h1">الحصص الأونلاين</h1>
      <p className="mt-1 text-body-sm text-text-muted">حضورك بيتسجل تلقائيًا لما تدخل الحصة من هنا.</p>

      <Tabs value={tab} onValueChange={(v) => setTab(v as LiveSessionStatusFilter)} dir="rtl" className="mt-6">
        <TabsList>
          {TABS.map((t) => <TabsTrigger key={t.value} value={t.value}>{t.label}</TabsTrigger>)}
        </TabsList>

        {TABS.map((t) => (
          <TabsContent key={t.value} value={t.value} className="mt-5">
            {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الحصص"} onRetry={() => refetch()} /> : null}
            {isLoading ? (
              <div className="flex flex-col gap-3">{[1, 2].map((i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
            ) : (sessions?.length || 0) === 0 ? (
              <EmptyState icon={Radio} title={`لا توجد حصص ${t.label}`} description="أي حصة جديدة هتظهر هنا." />
            ) : (
              <div className="flex flex-col gap-3">
                {sessions?.map((session) => (
                  <div key={session.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-h3">{session.title}</h3>
                        {tab === "live" ? <Badge tone="danger"><span className="live-dot" /> لايف الآن</Badge> : null}
                      </div>
                      <p className="mt-1 text-caption text-text-muted">{session.course_title}</p>
                      <p className="mt-1 flex items-center gap-1.5 text-caption text-text-muted">
                        <Calendar size={13} /> {new Date(session.starts_at).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" })}
                      </p>
                      {session.my_attendance.status !== "unmarked" ? (
                        <Badge tone={session.my_attendance.status === "present" ? "success" : session.my_attendance.status === "late" ? "warning" : "neutral"} className="mt-2">
                          {{ present: "سجّلت حضور", late: "سجّلت حضور متأخر", absent: "غائب", excused: "بعذر" }[session.my_attendance.status]}
                        </Badge>
                      ) : null}
                    </div>
                    <div>
                      {tab === "ended" ? (
                        session.recording_url ? (
                          <Button variant="secondary" asChild>
                            <a href={session.recording_url} target="_blank" rel="noreferrer"><PlayCircle size={16} /> مشاهدة التسجيل</a>
                          </Button>
                        ) : null
                      ) : (
                        <Button onClick={() => handleJoin(session)} disabled={!session.can_join} loading={joiningId === session.id}>
                          <ExternalLink size={16} /> {session.can_join ? "دخول الحصة" : "لسه معادش فتح"}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
