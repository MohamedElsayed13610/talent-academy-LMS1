"use client";

import { Bell, CheckCheck } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { useMarkAllNotificationsRead, useMarkNotificationRead, useMyNotifications } from "@/hooks/use-notifications";
import { ApiError } from "@/lib/api";
import { formatCairo } from "@/lib/cairo-time";

export default function NotificationsPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useMyNotifications(page);
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  const items = data?.items || [];
  const hasUnread = items.some((n) => !n.is_read);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-h1">الإشعارات</h1>
          <p className="mt-1 text-body-sm text-text-muted">إعلانات الإدارة الموجهة لك، لكورساتك، أو لمجموعتك.</p>
        </div>
        {hasUnread ? (
          <Button variant="secondary" size="sm" onClick={() => markAllRead.mutate()} loading={markAllRead.isPending}>
            <CheckCheck size={15} /> تعليم الكل كمقروء
          </Button>
        ) : null}
      </div>

      <div className="mt-6">
        {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الإشعارات"} onRetry={() => refetch()} /> : null}
        {isLoading ? (
          <div className="flex flex-col gap-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full" />)}</div>
        ) : items.length === 0 ? (
          <EmptyState icon={Bell} title="لا يوجد إشعارات" description="أي إعلان جديد من الإدارة هيظهر هنا." />
        ) : (
          <div className="flex flex-col gap-2">
            {items.map((n) => (
              <div
                key={n.id}
                className={`flex flex-col gap-1 rounded-lg border p-4 ${n.is_read ? "border-border bg-surface" : "border-primary-soft bg-primary-soft"}`}
                onClick={() => !n.is_read && markRead.mutate(n.id)}
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-h3">{n.title}</h3>
                  {!n.is_read ? <Badge tone="primary">جديد</Badge> : null}
                </div>
                {n.body ? <p className="text-body-sm text-text-muted">{n.body}</p> : null}
                <div className="flex items-center gap-2 text-caption text-text-subtle">
                  <span>{formatCairo(n.created_at)}</span>
                  {n.course_title ? <span>· {n.course_title}</span> : null}
                  {n.group_name ? <span>· {n.group_name}</span> : null}
                </div>
              </div>
            ))}
          </div>
        )}
        {data ? <div className="mt-3"><Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} /></div> : null}
      </div>
    </div>
  );
}
