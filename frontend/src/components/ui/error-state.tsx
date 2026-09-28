import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-danger-soft bg-danger-soft py-10 px-6 text-center">
      <AlertTriangle className="text-danger-fg" size={24} />
      <p className="text-body-sm text-danger-fg">{message}</p>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          إعادة المحاولة
        </Button>
      ) : null}
    </div>
  );
}
