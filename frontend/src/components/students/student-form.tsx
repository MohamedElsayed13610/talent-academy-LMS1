"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCourses } from "@/hooks/use-courses";
import { ApiError } from "@/lib/api";
import type { StudentCreateInput, StudentDetail, StudentUpdateInput } from "@/lib/types";

interface StudentFormProps {
  mode: "create" | "edit";
  initial?: StudentDetail;
  loading?: boolean;
  error?: ApiError | null;
  onSubmit: (payload: StudentCreateInput & StudentUpdateInput) => void;
}

/** The actual fields — no Dialog chrome, so it can be dropped inline (student detail page) or
 * wrapped in a drawer (StudentFormDrawer, used by the students list page). Shared by create/edit
 * since the fields overlap almost entirely. */
export function StudentFormFields({ mode, initial, loading, error, onSubmit }: StudentFormProps) {
  const { data: courses } = useCourses();
  const [courseId, setCourseId] = useState<string>("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: StudentCreateInput & StudentUpdateInput = {
      full_name: String(form.get("full_name") || "").trim(),
      email: String(form.get("email") || "").trim() || null,
      guardian_phone: String(form.get("guardian_phone") || "").trim(),
      grade_level: (String(form.get("grade_level") || "") || null) as StudentCreateInput["grade_level"],
      student_type: String(form.get("student_type") || "academy") as StudentCreateInput["student_type"],
      subscription_status: String(form.get("subscription_status") || "active") as StudentCreateInput["subscription_status"],
      subscription_expires_at: String(form.get("subscription_expires_at") || "").trim()
        ? new Date(`${form.get("subscription_expires_at")}T23:59:59`).toISOString()
        : null,
      admin_notes: String(form.get("admin_notes") || "").trim(),
    };
    if (mode === "create") {
      const password = String(form.get("password") || "").trim();
      if (password) payload.password = password;
      if (courseId) payload.course_ids = [Number(courseId)];
    } else {
      payload.student_code = String(form.get("student_code") || "").trim();
    }
    onSubmit(payload);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      {mode === "edit" ? (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="student_code">Student ID</Label>
          <Input id="student_code" name="student_code" dir="ltr" required minLength={1} maxLength={32} defaultValue={initial?.student_code || ""} placeholder="TA-000123" autoCapitalize="characters" />
        </div>
      ) : null}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="full_name">اسم الطالب</Label>
        <Input id="full_name" name="full_name" required minLength={2} defaultValue={initial?.full_name || ""} placeholder="محمد أحمد" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="grade_level">الصف الدراسي</Label>
          <select id="grade_level" name="grade_level" defaultValue={initial?.grade_level || ""} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            <option value="">غير محدد</option>
            <option value="G10">G10</option>
            <option value="G11">G11</option>
            <option value="G12">G12</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="student_type">نوع الطالب</Label>
          <select id="student_type" name="student_type" defaultValue={initial?.student_type || "academy"} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            <option value="academy">طالب الأكاديمية</option>
            <option value="external">طالب خارجي</option>
          </select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="subscription_status">حالة الاشتراك</Label>
          <select id="subscription_status" name="subscription_status" defaultValue={initial?.subscription_status || "active"} className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            <option value="active">نشط</option>
            <option value="pending">قيد الانتظار</option>
            <option value="expired">منتهي</option>
            <option value="suspended">موقوف</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="subscription_expires_at">انتهاء الاشتراك (اختياري)</Label>
          <Input id="subscription_expires_at" name="subscription_expires_at" type="date" defaultValue={initial?.subscription_expires_at?.slice(0, 10) || ""} />
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="email">البريد الإلكتروني (اختياري)</Label>
        <Input id="email" name="email" type="email" dir="ltr" defaultValue={initial?.email || ""} placeholder="student@example.com" />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="guardian_phone">رقم ولي الأمر</Label>
        <Input id="guardian_phone" name="guardian_phone" type="tel" dir="ltr" defaultValue={initial?.guardian_phone || ""} placeholder="+20 100 000 0000" />
      </div>
      {mode === "create" ? (
        <>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="password">كلمة المرور (اختياري)</Label>
            <Input id="password" name="password" type="text" dir="ltr" minLength={8} placeholder="اتركه فارغًا لتوليد كلمة مرور تلقائيًا" />
          </div>
          {courses && courses.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              <Label>الكورس الأول (اختياري)</Label>
              <Select value={courseId} onValueChange={setCourseId}>
                <SelectTrigger>
                  <SelectValue placeholder="بدون كورس مباشر" />
                </SelectTrigger>
                <SelectContent>
                  {courses.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
        </>
      ) : null}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="admin_notes">ملاحظات الإدارة</Label>
        <Textarea id="admin_notes" name="admin_notes" rows={3} defaultValue={initial?.admin_notes || ""} placeholder="ملاحظات داخلية لا تظهر للطالب" />
      </div>

      {error ? <p role="alert" className="rounded-md bg-danger-soft px-3.5 py-2.5 text-body-sm text-danger-fg">{error.message}</p> : null}

      <Button size="lg" loading={loading} className="mt-2">
        {mode === "create" ? "إنشاء حساب الطالب" : "حفظ التعديلات"}
      </Button>
    </form>
  );
}

/** Drawer wrapper used by the students list page (create/edit in a side sheet). */
export function StudentFormDrawer(props: StudentFormProps) {
  return (
    <DialogContent side="end">
      <DialogHeader>
        <DialogTitle>{props.mode === "create" ? "إضافة طالب جديد" : `تعديل ${props.initial?.full_name}`}</DialogTitle>
        <DialogDescription>
          {props.mode === "create" ? "سيتم توليد Student ID تلقائيًا بصيغة TA-000001 عند الإنشاء." : "الصف بيانات فقط ولا يضيف الطالب تلقائيًا لأي مجموعة أو كورس."}
        </DialogDescription>
      </DialogHeader>
      <StudentFormFields {...props} />
    </DialogContent>
  );
}
