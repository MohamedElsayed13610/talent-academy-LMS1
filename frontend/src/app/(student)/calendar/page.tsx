"use client";

import Link from "next/link";
import { CalendarDays, ChevronLeft, ChevronRight, FileQuestion, Radio } from "lucide-react";
import { useMemo, useState } from "react";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyCalendar } from "@/hooks/use-calendar";
import { ApiError } from "@/lib/api";
import type { CalendarEventOut } from "@/lib/types";

const WEEKDAYS = ["أحد", "اثنين", "ثلاثاء", "أربعاء", "خميس", "جمعة", "سبت"];
const MONTH_NAMES = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];

function dayKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

export default function CalendarPage() {
  const [cursor, setCursor] = useState(() => { const d = new Date(); d.setDate(1); return d; });
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const monthStart = useMemo(() => new Date(cursor.getFullYear(), cursor.getMonth(), 1), [cursor]);
  const monthEnd = useMemo(() => new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0, 23, 59, 59), [cursor]);
  const gridStart = useMemo(() => { const d = new Date(monthStart); d.setDate(d.getDate() - d.getDay()); return d; }, [monthStart]);
  const gridDays = useMemo(() => Array.from({ length: 42 }, (_, i) => { const d = new Date(gridStart); d.setDate(d.getDate() + i); return d; }), [gridStart]);

  const { data: events, isLoading, error, refetch } = useMyCalendar(monthStart.toISOString(), monthEnd.toISOString());

  const eventsByDay = useMemo(() => {
    const map = new Map<string, CalendarEventOut[]>();
    for (const e of events || []) {
      const key = dayKey(new Date(e.starts_at));
      map.set(key, [...(map.get(key) || []), e]);
    }
    return map;
  }, [events]);

  const agenda = useMemo(() => [...(events || [])].sort((a, b) => a.starts_at.localeCompare(b.starts_at)), [events]);
  const selectedEvents = selectedDay ? eventsByDay.get(selectedDay) || [] : [];

  return (
    <div>
      <h1 className="text-h1">الجدول</h1>
      <p className="mt-1 text-body-sm text-text-muted">حصصك وامتحاناتك القادمة في مكان واحد.</p>

      {error ? <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الجدول"} onRetry={() => refetch()} /> : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="mb-4 flex items-center justify-between">
            <button type="button" onClick={() => setCursor((c) => new Date(c.getFullYear(), c.getMonth() - 1, 1))} className="rounded-md p-2 hover:bg-surface-2" aria-label="الشهر السابق">
              <ChevronRight size={18} className="rtl-flip" />
            </button>
            <h2 className="text-h3">{MONTH_NAMES[cursor.getMonth()]} {cursor.getFullYear()}</h2>
            <button type="button" onClick={() => setCursor((c) => new Date(c.getFullYear(), c.getMonth() + 1, 1))} className="rounded-md p-2 hover:bg-surface-2" aria-label="الشهر التالي">
              <ChevronLeft size={18} className="rtl-flip" />
            </button>
          </div>

          {isLoading ? (
            <Skeleton className="h-96 w-full" />
          ) : (
            <div className="grid grid-cols-7 gap-1 text-center">
              {WEEKDAYS.map((w) => <div key={w} className="py-1 text-caption text-text-subtle">{w}</div>)}
              {gridDays.map((d) => {
                const key = dayKey(d);
                const inMonth = d.getMonth() === cursor.getMonth();
                const dayEvents = eventsByDay.get(key) || [];
                const isToday = key === dayKey(new Date());
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setSelectedDay(dayEvents.length > 0 ? key : null)}
                    className={`flex min-h-16 flex-col items-center gap-1 rounded-md p-1.5 text-body-sm transition-colors ${inMonth ? "" : "text-text-subtle opacity-50"} ${selectedDay === key ? "bg-primary-soft" : "hover:bg-surface-2"}`}
                  >
                    <span className={isToday ? "flex size-6 items-center justify-center rounded-full bg-primary text-primary-fg" : ""}>{d.getDate()}</span>
                    {dayEvents.length > 0 ? (
                      <span className="flex gap-0.5">
                        {dayEvents.slice(0, 3).map((e, i) => <span key={i} className={`size-1.5 rounded-full ${e.type === "live" ? "bg-info-fg" : "bg-accent-fg"}`} />)}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div>
          <h3 className="mb-3 text-h3">{selectedDay ? "أحداث اليوم" : "كل الأحداث هذا الشهر"}</h3>
          {(selectedDay ? selectedEvents : agenda).length === 0 ? (
            <EmptyState icon={CalendarDays} title="لا يوجد أحداث" description="مفيش حصص أو امتحانات مجدولة." />
          ) : (
            <div className="flex flex-col gap-2">
              {(selectedDay ? selectedEvents : agenda).map((e) => (
                <Link key={e.id} href={e.href} className="flex items-start gap-2.5 rounded-md border border-border p-3 text-body-sm hover:bg-surface-2">
                  {e.type === "live" ? <Radio size={16} className="mt-0.5 shrink-0 text-info-fg" /> : <FileQuestion size={16} className="mt-0.5 shrink-0 text-accent-fg" />}
                  <div>
                    <div className="font-medium">{e.title}</div>
                    <div className="text-caption text-text-muted">{e.course_title}</div>
                    <div className="text-caption text-text-subtle">{new Date(e.starts_at).toLocaleString("ar-EG", { dateStyle: "medium", timeStyle: "short" })}</div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
