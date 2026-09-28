"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  CalendarDays,
  LayoutDashboard,
  LogOut,
  Menu,
  PlayCircle,
  Radio,
  ScrollText,
  Trophy,
  User,
  X,
} from "lucide-react";
import { useState, type ComponentType } from "react";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { useLogout, useMe } from "@/hooks/use-auth";

type NavItem = { href: string; label: string; icon: ComponentType<{ size?: number }> };

// Bottom nav = the 5 most-used items on mobile; the rest live in the sheet (DESIGN.md §7).
const bottomNav: NavItem[] = [
  { href: "/dashboard", label: "الرئيسية", icon: LayoutDashboard },
  { href: "/courses", label: "الكورسات", icon: PlayCircle },
  { href: "/live", label: "الحصص", icon: Radio },
  { href: "/exams", label: "الامتحانات", icon: ScrollText },
  { href: "/points", label: "النقاط", icon: Trophy },
];

const allNav: NavItem[] = [
  ...bottomNav,
  { href: "/lessons", label: "الدروس", icon: PlayCircle },
  { href: "/calendar", label: "الجدول", icon: CalendarDays },
  { href: "/notifications", label: "الإشعارات", icon: Bell },
  { href: "/profile", label: "الملف الشخصي", icon: User },
];

export function StudentShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: me } = useMe();
  const logout = useLogout();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <div className="min-h-dvh bg-bg">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-4">
          <Brand compact />
          <nav className="hidden items-center gap-1 lg:flex" aria-label="التنقل الرئيسي">
            {allNav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-md px-3 py-2 text-body-sm font-medium transition-colors ${
                  isActive(item.href) ? "bg-primary-soft text-primary-soft-fg" : "text-text-muted hover:bg-surface-2"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {me ? (
              <span className="hidden text-body-sm text-text-muted sm:inline">{me.full_name}</span>
            ) : null}
            <button
              onClick={() => logout.mutate()}
              aria-label="تسجيل الخروج"
              className="hidden size-10 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-surface-2 hover:text-danger-fg lg:flex"
            >
              <LogOut size={19} />
            </button>
            <button
              onClick={() => setOpen(true)}
              aria-label="فتح القائمة"
              className="flex size-10 items-center justify-center rounded-md text-text-muted hover:bg-surface-2 lg:hidden"
            >
              <Menu size={22} />
            </button>
          </div>
        </div>
      </header>

      {open ? (
        <button aria-label="إغلاق القائمة" onClick={() => setOpen(false)} className="fixed inset-0 z-40 bg-black/40 lg:hidden" />
      ) : null}
      <aside
        className={`fixed inset-y-0 end-0 z-50 flex w-72 flex-col gap-1 bg-surface-raised p-4 shadow-[var(--shadow-3)] transition-transform duration-[var(--t-slow)] lg:hidden ${
          open ? "translate-x-0" : "translate-x-full rtl:-translate-x-full"
        }`}
      >
        <div className="mb-3 flex items-center justify-between">
          <Brand compact />
          <button aria-label="إغلاق" onClick={() => setOpen(false)} className="size-9 rounded-md hover:bg-surface-2">
            <X size={19} className="mx-auto" />
          </button>
        </div>
        {allNav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setOpen(false)}
            className={`flex items-center gap-3 rounded-md px-3 py-3 text-body-sm font-medium ${
              isActive(item.href) ? "bg-primary-soft text-primary-soft-fg" : "text-text"
            }`}
          >
            <item.icon size={18} />
            {item.label}
          </Link>
        ))}
        <button
          onClick={() => logout.mutate()}
          className="mt-2 flex items-center gap-3 rounded-md px-3 py-3 text-body-sm font-medium text-danger-fg"
        >
          <LogOut size={18} />
          تسجيل الخروج
        </button>
      </aside>

      <main className="mx-auto max-w-[1200px] px-4 pb-24 pt-6 lg:pb-10">{children}</main>

      <nav
        className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-surface lg:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        aria-label="التنقل السفلي"
      >
        {bottomNav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-1 flex-col items-center gap-1 py-2.5 text-caption ${
              isActive(item.href) ? "text-primary" : "text-text-muted"
            }`}
          >
            <item.icon size={21} />
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
