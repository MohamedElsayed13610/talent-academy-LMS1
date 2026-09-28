"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
}

// Every destructive admin action (delete student/group/course, bulk delete) goes through this —
// DESIGN.md §6 ConfirmDialog: shows a delete-preview's counts and needs an explicit confirm click.
export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = "تأكيد", cancelLabel = "إلغاء", destructive, loading, onConfirm }: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button variant={destructive ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Small helper for pages that need one reusable confirm dialog for several actions. */
export function useConfirmDialog() {
  const [state, setState] = useState<{ open: boolean; payload: unknown } | null>(null);
  return {
    isOpen: !!state?.open,
    payload: state?.payload,
    open: (payload?: unknown) => setState({ open: true, payload }),
    close: () => setState(null),
  };
}
