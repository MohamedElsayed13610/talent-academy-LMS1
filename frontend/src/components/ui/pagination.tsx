import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Pagination({ page, pageSize, total, onPageChange }: { page: number; pageSize: number; total: number; onPageChange: (page: number) => void }) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  if (pageCount <= 1) return null;

  return (
    <div className="flex items-center justify-between gap-3 border-t border-border pt-4 text-body-sm text-text-muted">
      <span>
        صفحة {page} من {pageCount} · {total} نتيجة
      </span>
      <div className="flex items-center gap-1">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPageChange(page - 1)} aria-label="السابق">
          <ChevronRight size={16} className="rtl-flip" />
        </Button>
        <Button variant="secondary" size="sm" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)} aria-label="التالي">
          <ChevronLeft size={16} className="rtl-flip" />
        </Button>
      </div>
    </div>
  );
}
