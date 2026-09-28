"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  ClipboardCheck,
  FileText,
  LogOut,
  Megaphone,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Radio,
  ScrollText,
  Settings,
  ShieldCheck,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";
import { useEffect, useState, type ComponentType } from "react";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { useLogout, useMe } from "@/hooks/use-auth";

type NavItem = { href: string; label: string; icon: ComponentType<{ size?: number }> };

const nav: NavItem[] = [
  { href: "/admin", label: "نظرة عامة", icon: ShieldCheck },
  { href: "/admin/students", label: "الطلاب", icon: UserRound },
  { href: "/admin/groups", label: "المجموعات", icon: UsersRound },
  { href: "/admin/courses", label: "الكورسات", icon: BookOpen },
  { href: "/admin/live", label: "الحصص", icon: Radio },
  { href: "/admin/attendance", label: "الحضور", icon: ClipboardCheck },
  { href: "/admin/exams", label: "الامتحانات", icon: ScrollText },
  { href: "/admin/reports", label: "التقارير", icon: FileText },
  { href: "/admin/announcements", label: "الإعلانات", icon: Megaphone },
  { href: "/admin/settings", label: "الإعدادات", icon: Settings },
];

export function AdminShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: me } = useMe();
  const logout = useLogout();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    // Same reasoning as ThemeToggle: read the per-viewer preference only after mount, so the
    // server-rendered first paint and the client's first render stay in sync.
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCollapsed(localStorage.getItem("talent-admin-sidebar") === "collapsed");
    } catch {
      // Private window / blocked storage — falls back to expanded, which is fine.
    }
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("talent-admin-sidebar", next ? "collapsed" : "open");
      } catch {
        // per-viewer convenience only — fine if it doesn't persist
      }
      return next;
    });
  }

  const isActive = (href: string) => (href === "/admin" ? pathname === "/admin" : pathname.startsWith(href));

  const sidebarContent = (
    <>
      <div className="flex items-center justify-between px-1 pb-4">
        {!collapsed && <Brand compact />}
        <button
          onClick={toggleCollapsed}
          aria-label={collapsed ? "توسيع القائمة" : "طي القائمة"}
          className="hidden size-9 items-center justify-center rounded-md text-text-muted hover:bg-surface-2 lg:flex"
        >
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
        <button
          onClick={() => setMobileOpen(false)}
          aria-label="إغلاق"
          className="flex size-9 items-center justify-center rounded-md text-text-muted hover:bg-surface-2 lg:hidden"
        >
          <X size={19} />
        </button>
      </div>
      <nav className="flex flex-1 flex-col gap-1" aria-label="قائمة الإدارة">
        {nav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setMobileOpen(false)}
            title={collapsed ? item.label : undefined}
            className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-body-sm font-medium transition-colors ${
              isActive(item.href) ? "bg-primary-soft text-primary-soft-fg" : "text-text-muted hover:bg-surface-2 hover:text-text"
            } ${collapsed ? "justify-center" : ""}`}
          >
            <item.icon size={18} />
            {!collapsed && item.label}
          </Link>
        ))}
      </nav>
      <button
        onClick={() => logout.mutate()}
        className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-body-sm font-medium text-danger-fg hover:bg-danger-soft ${collapsed ? "justify-center" : ""}`}
      >
        <LogOut size={18} />
        {!collapsed && "تسجيل الخروج"}
      </button>
    </>
  );

  return (
    <div className="flex min-h-dvh bg-bg">
      <aside className={`hidden shrink-0 flex-col border-e border-border bg-surface p-3 transition-[width] duration-[var(--t)] lg:flex ${collapsed ? "w-[72px]" : "w-[264px]"}`}>
        {sidebarContent}
      </aside>

      {mobileOpen ? (
        <button aria-label="إغلاق القائمة" onClick={() => setMobileOpen(false)} className="fixed inset-0 z-40 bg-black/40 lg:hidden" />
      ) : null}
      <aside
        className={`fixed inset-y-0 start-0 z-50 flex w-72 flex-col border-e border-border bg-surface p-3 shadow-[var(--shadow-3)] transition-transform duration-[var(--t-slow)] lg:hidden ${
          mobileOpen ? "translate-x-0" : "-translate-x-full rtl:translate-x-full"
        }`}
      >
        {sidebarContent}
      </aside>

      <div className="flex min-h-dvh flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-surface/95 px-4 backdrop-blur">
          <button
            onClick={() => setMobileOpen(true)}
            aria-label="فتح القائمة"
            className="flex size-10 items-center justify-center rounded-md text-text-muted hover:bg-surface-2 lg:hidden"
          >
            <Menu size={22} />
          </button>
          <span className="hidden text-body-sm text-text-muted lg:inline">لوحة الإدارة</span>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {me ? (
              <Link
                href="/change-password"
                title="تغيير كلمة المرور"
                className="rounded-md px-2 py-1.5 text-body-sm text-text-muted transition-colors hover:bg-surface-2 hover:text-text"
              >
                {me.full_name}
              </Link>
            ) : null}
          </div>
        </header>
        <main className="flex-1 p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
