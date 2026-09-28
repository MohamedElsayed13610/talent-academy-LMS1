"use client";

import Link from "next/link";
import { ArrowLeft, Eye, EyeOff, IdCard, LockKeyhole } from "lucide-react";
import { FormEvent, useState } from "react";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useLogin } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const login = useLogin();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [showPassword, setShowPassword] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate({ identifier, password, remember });
  }

  const errorMessage =
    login.error instanceof ApiError ? login.error.message : login.isError ? "تعذر تسجيل الدخول" : null;

  return (
    <main className="grid min-h-dvh lg:grid-cols-2">
      <section className="flex flex-col justify-center gap-8 p-6 sm:p-10 lg:p-16">
        <div className="flex items-center justify-between">
          <Brand />
          <Link href="/" className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
            العودة للموقع <ArrowLeft size={16} className="rtl-flip" />
          </Link>
        </div>

        <div className="mx-auto w-full max-w-sm">
          <span className="text-overline text-primary">STUDENT PORTAL</span>
          <h1 className="mt-2 text-h1">أهلًا بيك من جديد 👋</h1>
          <p className="mt-2 text-body-sm text-text-muted">الطالب يدخل بالـ Student ID، والأدمن يقدر يدخل بإيميل الإدارة.</p>

          <form onSubmit={submit} className="mt-8 flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="identifier">Student ID / Admin Email</Label>
              <div className="relative">
                <IdCard size={18} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
                <Input
                  id="identifier"
                  dir="ltr"
                  className="ps-10"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  required
                  placeholder="TA-000123"
                  autoCapitalize="characters"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">كلمة المرور</Label>
              <div className="relative">
                <LockKeyhole size={18} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
                <Input
                  id="password"
                  dir="ltr"
                  type={showPassword ? "text" : "password"}
                  className="ps-10 pe-10"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label="إظهار كلمة المرور"
                  className="absolute end-3 top-1/2 -translate-y-1/2 text-text-subtle hover:text-text"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-body-sm">
              <label className="flex items-center gap-2 text-text-muted">
                <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="size-4 rounded border-border" />
                تذكرني
              </label>
              <span className="text-text-subtle">لو نسيت الباسورد تواصل مع الأكاديمية.</span>
            </div>

            {errorMessage ? (
              <p role="alert" className="rounded-md bg-danger-soft px-3.5 py-2.5 text-body-sm text-danger-fg">
                {errorMessage}
              </p>
            ) : null}

            <Button size="lg" loading={login.isPending} className="mt-2">
              تسجيل الدخول <ArrowLeft size={18} className="rtl-flip" />
            </Button>
          </form>
        </div>
      </section>

      <aside className="relative hidden overflow-hidden bg-[var(--brand-900)] lg:flex lg:flex-col lg:justify-end lg:p-16">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{ background: "radial-gradient(circle at 30% 20%, var(--brand-600), transparent 60%)" }}
        />
        <blockquote className="relative z-10 text-display text-white">
          كل خطوة صغيرة
          <br />
          بتقرّبك من الكلية
          <br />
          اللي بتحلم بيها.
        </blockquote>
        <p className="relative z-10 mt-4 text-body-lg text-[var(--brand-200)]">Talent Academy</p>
        <div className="relative z-10 mt-10 flex items-center gap-3 rounded-lg bg-white/10 px-5 py-4 text-white backdrop-blur">
          <strong className="text-overline ltr">EST · SAT · ACT</strong>
          <span className="text-body-sm text-[var(--brand-200)]">Learn · Practice · Progress</span>
        </div>
      </aside>
    </main>
  );
}
