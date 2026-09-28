"use client";

import {
  Award,
  BookOpen,
  CalendarClock,
  CheckCircle2,
  Clock3,
  GraduationCap,
  Radio,
  ScrollText,
  Search,
  Trophy,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ProgressRing } from "@/components/ui/progress-ring";
import { StatTile } from "@/components/ui/stat-tile";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const colorGroups: { title: string; swatches: { name: string; varName: string }[] }[] = [
  {
    title: "Brand",
    swatches: [
      { name: "brand-50", varName: "--brand-50" },
      { name: "brand-100", varName: "--brand-100" },
      { name: "brand-300", varName: "--brand-300" },
      { name: "brand-500", varName: "--brand-500" },
      { name: "brand-600 (primary)", varName: "--brand-600" },
      { name: "brand-800", varName: "--brand-800" },
      { name: "brand-950", varName: "--brand-950" },
    ],
  },
  {
    title: "Gold (points/rank only)",
    swatches: [
      { name: "gold-400", varName: "--gold-400" },
      { name: "gold-500", varName: "--gold-500" },
      { name: "gold-600", varName: "--gold-600" },
    ],
  },
  {
    title: "Status",
    swatches: [
      { name: "success", varName: "--success-fg" },
      { name: "warning", varName: "--warning-fg" },
      { name: "danger", varName: "--danger-fg" },
      { name: "info", varName: "--info-fg" },
      { name: "live", varName: "--live" },
    ],
  },
];

const courseAccents = ["blue", "navy", "sky", "teal", "gold", "violet", "rose"] as const;

function Section({ title, kicker, children }: { title: string; kicker: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-5 border-t border-border py-10 first:border-t-0 first:pt-0">
      <div>
        <span className="text-overline text-primary">{kicker}</span>
        <h2 className="mt-1 text-h2">{title}</h2>
      </div>
      {children}
    </section>
  );
}

export default function DesignPreviewPage() {
  return (
    <div className="mx-auto max-w-[1100px] px-4 pb-24 pt-8">
      <header className="flex items-center justify-between border-b border-border pb-6">
        <div>
          <Brand />
          <p className="mt-3 max-w-xl text-body-sm text-text-muted">
            معاينة نظام التصميم — Phase 1. هذه الصفحة تجمع كل الـ tokens والمكوّنات الأساسية قبل بناء باقي الصفحات.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <Section kicker="TOKENS" title="الألوان">
        <div className="flex flex-col gap-6">
          {colorGroups.map((group) => (
            <div key={group.title}>
              <h3 className="text-label text-text-muted">{group.title}</h3>
              <div className="mt-2 flex flex-wrap gap-3">
                {group.swatches.map((swatch) => (
                  <div key={swatch.name} className="flex w-28 flex-col items-center gap-1.5 text-center">
                    <span
                      className="h-14 w-full rounded-md border border-border"
                      style={{ background: `var(${swatch.varName})` }}
                    />
                    <span className="text-caption ltr">{swatch.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div>
            <h3 className="text-label text-text-muted">Course accents (7 tokens, DESIGN.md A14)</h3>
            <div className="mt-2 flex flex-wrap gap-3">
              {courseAccents.map((accent) => (
                <span
                  key={accent}
                  className="rounded-full px-3.5 py-1.5 text-body-sm font-medium ltr"
                  style={{ background: `var(--accent-${accent}-soft)`, color: `var(--accent-${accent}-fg)` }}
                >
                  {accent}
                </span>
              ))}
            </div>
          </div>
        </div>
      </Section>

      <Section kicker="TOKENS" title="الخط والمقاسات">
        <div className="flex flex-col gap-3">
          <p className="text-display">Display — أهلاً بيك من جديد</p>
          <p className="text-h1">H1 — نظرة عامة على الكورسات</p>
          <p className="text-h2">H2 — الامتحانات القادمة</p>
          <p className="text-h3">H3 — SAT Math Basics</p>
          <p className="text-body-lg">Body Large — نص الأسئلة داخل الامتحان يستخدم هذا المقاس لراحة القراءة.</p>
          <p>Body — النص الأساسي لكل الواجهة، 16px بارتفاع سطر 1.7.</p>
          <p className="text-body-sm">Body Small — نصوص الجداول والتفاصيل الثانوية.</p>
          <p className="text-caption">Caption — 12 سبتمبر، 2026 · منذ يومين</p>
          <p className="text-overline">OVERLINE / EXAM SECURITY</p>
          <p className="text-metric tabular-nums ltr">482</p>
        </div>
      </Section>

      <Section kicker="COMPONENTS" title="الأزرار">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary">إجراء رئيسي</Button>
          <Button variant="secondary">إجراء ثانوي</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">حذف</Button>
          <Button variant="gold">
            <Trophy size={16} /> النقاط
          </Button>
          <Button loading>جاري الحفظ...</Button>
          <Button disabled>معطّل</Button>
          <Button size="sm">صغير</Button>
          <Button size="lg">كبير</Button>
        </div>
      </Section>

      <Section kicker="COMPONENTS" title="الحالات والشارات">
        <div className="flex flex-wrap gap-2">
          <Badge tone="success">حاضر</Badge>
          <Badge tone="warning">متأخر</Badge>
          <Badge tone="danger">غائب</Badge>
          <Badge tone="info">بعذر</Badge>
          <Badge tone="neutral">غير محدد</Badge>
          <Badge tone="primary">منشور</Badge>
          <Badge tone="accent">
            <Award size={13} /> +20 نقطة
          </Badge>
        </div>
      </Section>

      <Section kicker="COMPONENTS" title="النماذج">
        <div className="grid max-w-sm gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="demo-search">بحث</Label>
            <div className="relative">
              <Search size={16} className="pointer-events-none absolute start-3.5 top-1/2 -translate-y-1/2 text-text-subtle" />
              <Input id="demo-search" className="ps-9" placeholder="ابحث بالاسم أو Student ID..." />
            </div>
          </div>
          <div className="flex items-center justify-between rounded-md border border-border px-4 py-3">
            <span className="text-body-sm">الوضع الليلي</span>
            <Switch />
          </div>
        </div>
      </Section>

      <Section kicker="COMPONENTS" title="البطاقات والمقاييس">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatTile icon={GraduationCap} label="إجمالي الطلاب" value={248} hint="حسابات ينشئها الأدمن" />
          <StatTile icon={BookOpen} label="الكورسات" value={12} />
          <StatTile icon={Radio} label="الحصص اللايف" value={4} />
          <StatTile icon={Trophy} label="نقاطي" value={482} tone="accent" hint="+7 هذا الأسبوع" />
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>SAT Math — Basics</CardTitle>
              <CardDescription>Algebra • Problem Solving</CardDescription>
            </CardHeader>
            <div className="flex items-center gap-4">
              <ProgressRing value={62} />
              <div className="flex flex-col gap-1 text-body-sm text-text-muted">
                <span className="flex items-center gap-1.5">
                  <BookOpen size={15} /> 12/19 درس
                </span>
                <span className="flex items-center gap-1.5">
                  <Clock3 size={15} /> مرن
                </span>
              </div>
            </div>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>الامتحان القادم</CardTitle>
              <CardDescription>EST English Unit 3</CardDescription>
            </CardHeader>
            <div className="flex items-center gap-2 text-body-sm text-text-muted">
              <CalendarClock size={16} /> الخميس 7:00م · 40 دقيقة
            </div>
            <Button size="sm" className="mt-4">
              <ScrollText size={16} /> عرض التفاصيل
            </Button>
          </Card>
        </div>
      </Section>

      <Section kicker="COMPONENTS" title="التبويبات">
        <Tabs defaultValue="all" dir="rtl">
          <TabsList>
            <TabsTrigger value="all">الكل</TabsTrigger>
            <TabsTrigger value="upcoming">قادم</TabsTrigger>
            <TabsTrigger value="ended">انتهى</TabsTrigger>
          </TabsList>
          <TabsContent value="all" className="mt-3 text-body-sm text-text-muted">
            كل العناصر.
          </TabsContent>
          <TabsContent value="upcoming" className="mt-3 text-body-sm text-text-muted">
            العناصر القادمة فقط.
          </TabsContent>
          <TabsContent value="ended" className="mt-3 text-body-sm text-text-muted">
            العناصر المنتهية فقط.
          </TabsContent>
        </Tabs>
      </Section>

      <Section kicker="STATES" title="حالات التحميل والفراغ والخطأ">
        <div className="grid gap-6 sm:grid-cols-3">
          <div className="flex flex-col gap-2">
            <span className="text-label text-text-muted">Skeleton</span>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-24 w-full" />
          </div>
          <div>
            <span className="text-label text-text-muted">Empty</span>
            <div className="mt-2">
              <EmptyState icon={ScrollText} title="لا توجد امتحانات حاليًا" description="أي امتحان جديد هيظهر هنا." />
            </div>
          </div>
          <div>
            <span className="text-label text-text-muted">Error</span>
            <div className="mt-2">
              <ErrorState message="تعذر تحميل البيانات" onRetry={() => {}} />
            </div>
          </div>
        </div>
      </Section>

      <Section kicker="EXAM" title="عنصر سؤال امتحان (نموذج)">
        <div className="max-w-md rounded-lg border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Badge tone="neutral">Q1</Badge>
              <Badge tone="neutral">1 pt</Badge>
              <Badge tone="info">Algebra</Badge>
            </div>
            <Badge tone="success">
              <CheckCircle2 size={13} /> Answered
            </Badge>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 ltr">
            {["A", "B", "C", "D"].map((letter, i) => (
              <button
                key={letter}
                className={`flex h-14 items-center justify-center rounded-md border text-h3 font-bold transition-colors ${
                  i === 1 ? "border-primary bg-primary-soft text-primary-soft-fg" : "border-border hover:bg-surface-2"
                }`}
              >
                {letter}
              </button>
            ))}
          </div>
        </div>
      </Section>
    </div>
  );
}
