import { Construction } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";

// Placeholder for routes that ship in a later phase (docs/ARCHITECTURE.md §18) — keeps the shell's
// navigation fully clickable during the Phase 1 design review instead of 404ing.
export function ComingSoon({ title }: { title: string }) {
  return (
    <div>
      <h1 className="text-h1">{title}</h1>
      <div className="mt-6">
        <EmptyState icon={Construction} title="هذه الصفحة قيد الإنشاء" description="هتتفعّل في مرحلة بناء لاحقة من المشروع." />
      </div>
    </div>
  );
}
