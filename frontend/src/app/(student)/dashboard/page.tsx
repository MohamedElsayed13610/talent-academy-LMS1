"use client";

import { useMe } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";

// Real dashboard content (progress rings, next session/exam, per-course points) ships in Phase 7
// once /me/dashboard exists (docs/ARCHITECTURE.md §5.2, §6.2). This confirms the shell + auth work.
export default function DashboardPage() {
  const { data: me, isLoading } = useMe();

  return (
    <div>
      {isLoading ? (
        <Skeleton className="h-9 w-64" />
      ) : (
        <h1 className="text-h1">أهلاً {me?.full_name.split(" ")[0]} 👋</h1>
      )}
      <p className="mt-2 text-body-sm text-text-muted">ملخص يومك الدراسي هيظهر هنا في مرحلة بناء لاحقة.</p>
    </div>
  );
}
