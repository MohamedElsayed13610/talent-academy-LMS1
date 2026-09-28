"use client";

import { useMe } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";

// Real overview (totals, attendance rate, recent activity) ships in Phase 2+ once /admin/overview
// exists (docs/ARCHITECTURE.md §5.3, §6.3). This confirms the admin shell + RBAC guard work.
export default function AdminOverviewPage() {
  const { data: me, isLoading } = useMe();

  return (
    <div>
      {isLoading ? <Skeleton className="h-9 w-72" /> : <h1 className="text-h1">مرحبًا {me?.full_name} — نظرة عامة</h1>}
      <p className="mt-2 text-body-sm text-text-muted">إحصائيات الأكاديمية هتظهر هنا في مرحلة بناء لاحقة.</p>
    </div>
  );
}
