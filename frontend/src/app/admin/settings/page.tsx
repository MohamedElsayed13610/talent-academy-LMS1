"use client";

import { useState } from "react";
import { Database, Plus, ScrollText, Settings2, ShieldCheck, Trash2, UserCog } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Label } from "@/components/ui/input";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useUploadFile } from "@/hooks/use-courses";
import {
  useAcademySettings, useAdminAccounts, useAuditLog, useBackupStatus, useCreateAdminAccount,
  useDeleteAdminAccount, useUpdateAcademySettings, useUpdateAdminAccount,
} from "@/hooks/use-admin-settings";
import { useMe } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { formatCairo } from "@/lib/cairo-time";
import type { AcademySettingsOut, AdminAccountOut } from "@/lib/types";

const POINT_LABELS: Record<string, string> = {
  lesson_complete: "إكمال درس", attendance_manual: "حضور (تسجيل يدوي)", attendance_on_time: "حضور في الميعاد",
  attendance_late: "حضور متأخر", exam_submit: "تسليم امتحان", exam_60_79: "امتحان ٦٠-٧٩٪",
  exam_80_89: "امتحان ٨٠-٨٩٪", exam_90_99: "امتحان ٩٠-٩٩٪", exam_100: "امتحان ١٠٠٪",
};

export default function AdminSettingsPage() {
  return (
    <div className="talent-admin-page">
      <header className="border-b border-border pb-6">
        <h1 className="text-h1">الإعدادات</h1>
        <p className="mt-1 text-body-sm text-text-muted">إعدادات الأكاديمية، حسابات الإدارة، وسجل النشاط.</p>
      </header>

      <Tabs defaultValue="branding" className="mt-6">
        <TabsList className="flex-wrap">
          <TabsTrigger value="branding"><Settings2 size={15} className="me-1.5 inline" /> العلامة التجارية</TabsTrigger>
          <TabsTrigger value="rules"><ShieldCheck size={15} className="me-1.5 inline" /> النقاط والحدود</TabsTrigger>
          <TabsTrigger value="admins"><UserCog size={15} className="me-1.5 inline" /> حسابات الإدارة</TabsTrigger>
          <TabsTrigger value="audit"><ScrollText size={15} className="me-1.5 inline" /> سجل النشاط</TabsTrigger>
          <TabsTrigger value="backup"><Database size={15} className="me-1.5 inline" /> النسخ الاحتياطي</TabsTrigger>
        </TabsList>

        <TabsContent value="branding" className="mt-6"><BrandingSection /></TabsContent>
        <TabsContent value="rules" className="mt-6"><RulesSection /></TabsContent>
        <TabsContent value="admins" className="mt-6"><AdminsSection /></TabsContent>
        <TabsContent value="audit" className="mt-6"><AuditSection /></TabsContent>
        <TabsContent value="backup" className="mt-6"><BackupSection /></TabsContent>
      </Tabs>
    </div>
  );
}

// ------------------------------------------------------------------------------------ branding ----

function BrandingSection() {
  const { data, isLoading, error, refetch } = useAcademySettings();
  const update = useUpdateAcademySettings();
  const upload = useUploadFile();
  // Only tracks explicit edits, not a copy of `data` — avoids the set-state-in-effect antipattern
  // (same derived-value approach as the student dashboard's course selector).
  const [edits, setEdits] = useState<{ display_name?: string; whatsapp_url?: string }>({});
  const form = data ? { display_name: edits.display_name ?? data.display_name, whatsapp_url: edits.whatsapp_url ?? data.whatsapp_url } : null;

  if (error) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الإعدادات"} onRetry={() => refetch()} />;
  if (isLoading || !data || !form) return <Skeleton className="h-64 w-full" />;

  async function save() {
    if (!form) return;
    try {
      await update.mutateAsync(form);
      setEdits({});
      toast.success("تم حفظ الإعدادات");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر الحفظ");
    }
  }

  async function onLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const uploaded = await upload.mutateAsync({ file, purpose: "logo" });
      await update.mutateAsync({ logo_file_id: uploaded.id });
      toast.success("تم تحديث الشعار");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر رفع الشعار");
    } finally {
      e.target.value = "";
    }
  }

  return (
    <Card className="max-w-xl">
      <CardHeader><CardTitle>العلامة التجارية</CardTitle></CardHeader>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-4">
          <div className="flex size-16 items-center justify-center overflow-hidden rounded-lg border border-border bg-surface-2">
            {data.logo_url ? (
              // logo_url 302-redirects to a fresh short-lived presigned R2/MinIO URL per request;
              // next/image's remote-pattern allowlist can't cover a host+query that changes on
              // every load, so a plain <img> is the only option here.
              // eslint-disable-next-line @next/next/no-img-element
              <img src={data.logo_url} alt="الشعار" className="size-full object-contain" />
            ) : (
              <Settings2 size={22} className="text-text-subtle" />
            )}
          </div>
          <div>
            <Label htmlFor="logo-upload" className="cursor-pointer text-body-sm text-primary hover:underline">رفع شعار جديد</Label>
            <input id="logo-upload" type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={onLogoChange} />
            <p className="text-caption text-text-subtle">PNG أو JPEG أو WEBP، أقل من 2 ميجابايت</p>
          </div>
        </div>

        <div>
          <Label htmlFor="display_name">اسم الأكاديمية</Label>
          <Input id="display_name" className="mt-1.5" value={form.display_name} onChange={(e) => setEdits((s) => ({ ...s, display_name: e.target.value }))} />
        </div>
        <div>
          <Label htmlFor="whatsapp_url">رابط واتساب</Label>
          <Input id="whatsapp_url" className="mt-1.5" placeholder="https://wa.me/2010..." value={form.whatsapp_url} onChange={(e) => setEdits((s) => ({ ...s, whatsapp_url: e.target.value }))} />
        </div>
        {data.updated_at ? <p className="text-caption text-text-subtle">آخر تحديث: {formatCairo(data.updated_at)}{data.updated_by_name ? ` — ${data.updated_by_name}` : ""}</p> : null}
        <Button className="self-start" onClick={save} loading={update.isPending}>حفظ</Button>
      </div>
    </Card>
  );
}

// --------------------------------------------------------------------------------------- rules ----

type RulesEdits = Partial<Pick<AcademySettingsOut, "point_values" | "late_threshold_minutes" | "violation_limit" | "join_open_minutes_before" | "exam_submit_grace_seconds">>;

function RulesSection() {
  const { data, isLoading, error, refetch } = useAcademySettings();
  const update = useUpdateAcademySettings();
  const [edits, setEdits] = useState<RulesEdits>({});
  const form: AcademySettingsOut | null = data ? { ...data, ...edits, point_values: { ...data.point_values, ...edits.point_values } } : null;

  if (error) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الإعدادات"} onRetry={() => refetch()} />;
  if (isLoading || !form) return <Skeleton className="h-96 w-full" />;

  async function save() {
    if (!form) return;
    try {
      await update.mutateAsync({
        point_values: form.point_values, late_threshold_minutes: form.late_threshold_minutes,
        violation_limit: form.violation_limit, join_open_minutes_before: form.join_open_minutes_before,
        exam_submit_grace_seconds: form.exam_submit_grace_seconds,
      });
      setEdits({});
      toast.success("تم حفظ الإعدادات");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر الحفظ");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card className="max-w-2xl">
        <CardHeader><CardTitle>قيم النقاط</CardTitle></CardHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.entries(form.point_values).map(([key, value]) => (
            <div key={key}>
              <Label htmlFor={`pv-${key}`}>{POINT_LABELS[key] || key}</Label>
              <Input
                id={`pv-${key}`} type="number" className="mt-1.5" value={value}
                onChange={(e) => setEdits((s) => ({ ...s, point_values: { ...form.point_values, [key]: Number(e.target.value) } }))}
              />
            </div>
          ))}
        </div>
      </Card>

      <Card className="max-w-2xl">
        <CardHeader><CardTitle>حدود الحضور والامتحانات</CardTitle></CardHeader>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="late_threshold">حد التأخير (دقائق)</Label>
            <Input id="late_threshold" type="number" className="mt-1.5" value={form.late_threshold_minutes} onChange={(e) => setEdits((s) => ({ ...s, late_threshold_minutes: Number(e.target.value) }))} />
          </div>
          <div>
            <Label htmlFor="violation_limit">حد مخالفات الامتحان</Label>
            <Input id="violation_limit" type="number" className="mt-1.5" value={form.violation_limit} onChange={(e) => setEdits((s) => ({ ...s, violation_limit: Number(e.target.value) }))} />
          </div>
          <div>
            <Label htmlFor="join_open">فتح الانضمام قبل الحصة (دقائق)</Label>
            <Input id="join_open" type="number" className="mt-1.5" value={form.join_open_minutes_before} onChange={(e) => setEdits((s) => ({ ...s, join_open_minutes_before: Number(e.target.value) }))} />
          </div>
          <div>
            <Label htmlFor="grace">مهلة تسليم الامتحان (ثواني)</Label>
            <Input id="grace" type="number" className="mt-1.5" value={form.exam_submit_grace_seconds} onChange={(e) => setEdits((s) => ({ ...s, exam_submit_grace_seconds: Number(e.target.value) }))} />
          </div>
        </div>
      </Card>

      <Button className="self-start" onClick={save} loading={update.isPending}>حفظ التغييرات</Button>
    </div>
  );
}

// -------------------------------------------------------------------------------------- admins ----

function AdminsSection() {
  const { data, isLoading, error, refetch } = useAdminAccounts();
  const { data: me } = useMe();
  const createAdmin = useCreateAdminAccount();
  const updateAdmin = useUpdateAdminAccount();
  const deleteAdmin = useDeleteAdminAccount();

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState({ full_name: "", email: "", title: "" });
  const [deleteTarget, setDeleteTarget] = useState<AdminAccountOut | null>(null);

  async function submitCreate() {
    try {
      const result = await createAdmin.mutateAsync({ full_name: form.full_name, email: form.email, title: form.title || undefined });
      toast.success(result.generated_password ? `تم إنشاء الحساب — كلمة المرور: ${result.generated_password}` : "تم إنشاء الحساب");
      setCreateOpen(false);
      setForm({ full_name: "", email: "", title: "" });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر إنشاء الحساب");
    }
  }

  async function toggleActive(admin: AdminAccountOut) {
    try {
      await updateAdmin.mutateAsync({ id: admin.id, payload: { is_active: !admin.is_active } });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر تحديث الحساب");
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      await deleteAdmin.mutateAsync(deleteTarget.id);
      toast.success("تم حذف الحساب");
      setDeleteTarget(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر حذف الحساب");
    }
  }

  if (error) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الحسابات"} onRetry={() => refetch()} />;
  if (isLoading) return <Skeleton className="h-64 w-full" />;

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => setCreateOpen(true)}><Plus size={16} /> حساب إداري جديد</Button>
      </div>

      {(data?.length || 0) === 0 ? (
        <EmptyState icon={UserCog} title="لا يوجد حسابات إدارية" description="أضف أول حساب إداري." />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          {data!.map((admin) => (
            <div key={admin.id} className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 text-body-sm last:border-b-0">
              <div>
                <div className="font-medium">{admin.full_name}{admin.id === me?.id ? <span className="text-text-subtle"> (أنت)</span> : null}</div>
                <div className="text-caption text-text-subtle">{admin.email}{admin.title ? ` · ${admin.title}` : ""}</div>
              </div>
              <div className="flex items-center gap-3">
                {admin.last_login_at ? <span className="text-caption text-text-subtle">آخر دخول {formatCairo(admin.last_login_at)}</span> : null}
                <Switch checked={admin.is_active} onCheckedChange={() => toggleActive(admin)} disabled={admin.id === me?.id} />
                <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(admin)} disabled={admin.id === me?.id}><Trash2 size={16} /></Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>حساب إداري جديد</DialogTitle></DialogHeader>
          <div className="flex flex-col gap-3">
            <div>
              <Label htmlFor="new-admin-name">الاسم الكامل</Label>
              <Input id="new-admin-name" className="mt-1.5" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="new-admin-email">البريد الإلكتروني</Label>
              <Input id="new-admin-email" type="email" className="mt-1.5" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="new-admin-title">المسمى الوظيفي (اختياري)</Label>
              <Input id="new-admin-title" className="mt-1.5" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <Button className="self-start" onClick={submitCreate} loading={createAdmin.isPending} disabled={!form.full_name || !form.email}>إنشاء</Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}
        title={`حذف حساب ${deleteTarget?.full_name || ""}؟`} destructive confirmLabel="حذف" loading={deleteAdmin.isPending}
        onConfirm={confirmDelete}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------------------- audit ----

function AuditSection() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error, refetch } = useAuditLog(page);

  if (error) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل سجل النشاط"} onRetry={() => refetch()} />;
  if (isLoading && !data) return <Skeleton className="h-64 w-full" />;
  if (!data || data.items.length === 0) return <EmptyState icon={ScrollText} title="لا يوجد نشاط مسجل بعد" description="أي إجراء إداري (إضافة، تعديل، حذف) هيظهر هنا." />;

  return (
    <div>
      <div className="overflow-hidden rounded-lg border border-border">
        {data.items.map((row) => (
          <div key={row.id} className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 text-body-sm last:border-b-0">
            <div>
              <span className="font-medium">{row.actor_label || "النظام"}</span>
              <span className="text-text-muted"> — {row.action}</span>
              <Badge tone="neutral" className="ms-2">{row.entity_type}#{row.entity_id}</Badge>
            </div>
            <span className="text-caption text-text-subtle">{formatCairo(row.created_at)}</span>
          </div>
        ))}
      </div>
      <div className="mt-3"><Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} /></div>
    </div>
  );
}

// --------------------------------------------------------------------------------------- backup ----

function BackupSection() {
  const { data, isLoading, error, refetch } = useBackupStatus();

  if (error) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل حالة النسخ الاحتياطي"} onRetry={() => refetch()} />;
  if (isLoading || !data) return <Skeleton className="h-40 w-full" />;

  return (
    <Card className="max-w-xl">
      <CardHeader><CardTitle>النسخ الاحتياطي</CardTitle></CardHeader>
      <div className="flex flex-col gap-3 text-body-sm">
        <div className="flex items-center justify-between rounded-md bg-surface-2 px-3.5 py-2.5">
          <span>الحالة</span>
          <Badge tone={data.configured ? "success" : "danger"}>{data.configured ? "مفعّل" : "غير مفعّل"}</Badge>
        </div>
        <div className="flex items-center justify-between rounded-md bg-surface-2 px-3.5 py-2.5">
          <span>آخر نسخة احتياطية</span>
          <span className="text-text-muted">{data.last_run_at ? formatCairo(data.last_run_at) : "لسه مفيش نسخة اتعملت"}</span>
        </div>
        {data.last_status ? (
          <div className="flex items-center justify-between rounded-md bg-surface-2 px-3.5 py-2.5">
            <span>نتيجة آخر تشغيل</span>
            <Badge tone={data.last_status === "ok" ? "success" : "danger"}>{data.last_status === "ok" ? "نجحت" : "فشلت"}</Badge>
          </div>
        ) : null}
        <p className="text-caption text-text-subtle">النسخ الاحتياطي يعمل تلقائيًا مرة كل يوم، ويُحفظ في تخزين منفصل عن قاعدة البيانات الأساسية.</p>
      </div>
    </Card>
  );
}
