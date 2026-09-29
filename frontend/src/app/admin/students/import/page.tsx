"use client";

import Link from "next/link";
import { ArrowRight, CheckCircle2, Download, FileSpreadsheet, UploadCloud, XCircle } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useImportCommit, useImportPreview } from "@/hooks/use-students";
import { api, ApiError, saveBlob } from "@/lib/api";
import type { ImportCommitResult, ImportPreview } from "@/lib/types";

export default function StudentImportPage() {
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportCommitResult | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const previewMutation = useImportPreview();
  const commitMutation = useImportCommit();

  // downloadTemplate/downloadCredentials call api.getBlob/postBlob directly (not through
  // useMutation), so they get no automatic error handling at all — each needs its own try/catch.
  async function downloadTemplate() {
    try {
      const { blob, filename } = await api.getBlob("/admin/students/import/template.xlsx");
      saveBlob(blob, filename || "students-template.xlsx");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر تحميل القالب");
    }
  }

  async function onFileSelected(file: File) {
    setResult(null);
    try {
      const data = await previewMutation.mutateAsync(file);
      setPreview(data);
    } catch {
      // rendered inline via previewMutation.error below (hooks/use-students.ts marks it silent)
    }
  }

  async function commit() {
    if (!preview) return;
    const validRows = preview.rows.filter((r) => r.errors.length === 0).map((r) => r.data);
    try {
      const data = await commitMutation.mutateAsync(validRows);
      setResult(data);
      setPreview(null);
    } catch {
      // toast already shown globally (app/providers.tsx MutationCache)
    }
  }

  async function downloadCredentials() {
    if (!result) return;
    const rows = result.created.filter((r) => r.generated_password).map((r) => ({ student_code: r.student_code, full_name: r.full_name, password: r.generated_password as string }));
    if (!rows.length) return;
    try {
      const { blob, filename } = await api.postBlob("/admin/students/credentials.xlsx", { rows });
      saveBlob(blob, filename || "student-credentials.xlsx");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "تعذر تحميل كلمات المرور");
    }
  }

  return (
    <div className="talent-admin-page max-w-3xl">
      <Link href="/admin/students" className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
        <ArrowRight size={16} className="rtl-flip" /> رجوع للطلاب
      </Link>

      <header className="mt-3 border-b border-border pb-6">
        <span className="text-overline text-primary">BULK IMPORT</span>
        <h1 className="mt-1 text-h1">استيراد طلاب من Excel</h1>
        <p className="mt-1 text-body-sm text-text-muted">حمّل القالب، املأه، ثم ارفعه هنا لمعاينة الأخطاء قبل الحفظ. حد أقصى 2000 صف / 2 ميجابايت.</p>
      </header>

      {!preview && !result ? (
        <section className="mt-6 flex flex-col items-center gap-4 rounded-lg border border-dashed border-border py-14 px-6 text-center">
          <UploadCloud size={32} className="text-primary" />
          <div className="flex flex-col gap-1">
            <Button variant="secondary" onClick={downloadTemplate}>
              <Download size={16} /> تحميل القالب
            </Button>
            <span className="text-caption">قالب Excel بأعمدة ثنائية اللغة</span>
          </div>
          <Button loading={previewMutation.isPending} onClick={() => fileInput.current?.click()}>
            <FileSpreadsheet size={16} /> اختر ملف Excel أو CSV
          </Button>
          <input ref={fileInput} type="file" accept=".xlsx,.csv" className="hidden" onChange={(e) => e.target.files?.[0] && onFileSelected(e.target.files[0])} />
          {previewMutation.error ? <p className="text-body-sm text-danger-fg">{(previewMutation.error as Error).message}</p> : null}
        </section>
      ) : null}

      {preview ? (
        <section className="mt-6">
          <div className="flex items-center justify-between rounded-md bg-surface-2 px-4 py-3 text-body-sm">
            <span>
              <Badge tone="success">{preview.valid_count} صحيح</Badge>{" "}
              {preview.error_count > 0 ? <Badge tone="danger">{preview.error_count} به أخطاء</Badge> : null}
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setPreview(null)}>إلغاء</Button>
              <Button size="sm" onClick={commit} loading={commitMutation.isPending} disabled={preview.valid_count === 0}>
                حفظ {preview.valid_count} طالب
              </Button>
            </div>
          </div>

          <div className="mt-4 overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-body-sm">
              <thead className="bg-surface-2 text-caption text-text-muted">
                <tr>
                  <th className="p-2 text-start">#</th>
                  <th className="p-2 text-start ltr">Student ID</th>
                  <th className="p-2 text-start">الاسم</th>
                  <th className="p-2 text-start">الحالة</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.row_no} className={`border-t border-border ${row.errors.length ? "bg-danger-soft/40" : ""}`}>
                    <td className="p-2 text-text-muted">{row.row_no}</td>
                    <td className="p-2 ltr text-text-muted">{row.data.student_code || "(تلقائي)"}</td>
                    <td className="p-2">{row.data.full_name}</td>
                    <td className="p-2">
                      {row.errors.length ? (
                        <span className="flex items-center gap-1 text-danger-fg"><XCircle size={14} /> {row.errors.join("، ")}</span>
                      ) : (
                        <span className="flex items-center gap-1 text-success-fg"><CheckCircle2 size={14} /> جاهز</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {result ? (
        <section className="mt-6 flex flex-col gap-4">
          <div className="rounded-md bg-success-soft px-4 py-3 text-body-sm text-success-fg">
            تم إنشاء {result.created.length} طالب{result.failed.length ? ` — فشل ${result.failed.length}` : ""}.
          </div>
          {result.created.some((r) => r.generated_password) ? (
            <Button variant="secondary" onClick={downloadCredentials}>
              <Download size={16} /> تحميل كلمات المرور (Excel)
            </Button>
          ) : null}
          <Button asChild><Link href="/admin/students">الذهاب لقائمة الطلاب</Link></Button>
        </section>
      ) : null}
    </div>
  );
}
