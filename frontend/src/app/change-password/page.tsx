"use client";

import Link from "next/link";
import { ArrowLeft, KeyRound } from "lucide-react";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useMe } from "@/hooks/use-auth";
import { api, ApiError } from "@/lib/api";
import type { LoginResponse } from "@/lib/types";

// Optional, self-service page — reachable from Profile (student) or the account menu (admin).
// Nothing redirects here automatically; must_change_password is informational only, not enforced.
export default function ChangePasswordPage() {
  const router = useRouter();
  const { data: me } = useMe();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [mismatchError, setMismatchError] = useState("");

  const backHref = me?.role === "admin" ? "/admin" : "/profile";

  const mutation = useMutation<LoginResponse, ApiError>({
    mutationFn: () => api.post<LoginResponse>("/auth/change-password", { current_password: currentPassword, new_password: newPassword }),
    onSuccess: (data) => {
      toast.success("تم تغيير كلمة المرور بنجاح");
      router.push(data.user.role === "admin" ? "/admin" : "/profile");
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    setMismatchError("");
    if (newPassword !== confirmPassword) {
      setMismatchError("كلمتا المرور غير متطابقتين");
      return;
    }
    mutation.mutate();
  }

  const errorMessage = mismatchError || (mutation.error instanceof ApiError ? mutation.error.message : null);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-bg px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center justify-between">
          <Brand compact />
          <Link href={backHref} className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
            <ArrowLeft size={16} className="rtl-flip" /> رجوع
          </Link>
        </div>
        <div className="rounded-lg border border-border bg-surface p-6 shadow-[var(--shadow-1)]">
          <span className="flex size-11 items-center justify-center rounded-full bg-primary-soft text-primary-soft-fg">
            <KeyRound size={20} />
          </span>
          <h1 className="mt-4 text-h2">تغيير كلمة المرور</h1>
          <p className="mt-1 text-body-sm text-text-muted">اختياري — غيّر كلمة مرورك في أي وقت تحب.</p>

          <form onSubmit={submit} className="mt-6 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="current">كلمة المرور الحالية</Label>
              <Input id="current" dir="ltr" type="password" required value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="new">كلمة المرور الجديدة</Label>
              <Input id="new" dir="ltr" type="password" required minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="confirm">تأكيد كلمة المرور</Label>
              <Input id="confirm" dir="ltr" type="password" required minLength={8} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
            </div>
            {errorMessage ? (
              <p role="alert" className="rounded-md bg-danger-soft px-3.5 py-2.5 text-body-sm text-danger-fg">
                {errorMessage}
              </p>
            ) : null}
            <Button size="lg" loading={mutation.isPending} className="mt-2">
              حفظ كلمة المرور الجديدة
            </Button>
          </form>
        </div>
      </div>
    </main>
  );
}
