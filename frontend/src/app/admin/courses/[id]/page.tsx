"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileText,
  Link as LinkIcon,
  Plus,
  Trash2,
  UploadCloud,
  UsersRound,
} from "lucide-react";
import Image from "next/image";
import { FormEvent, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  useAddLesson,
  useAddMaterial,
  useAddSection,
  useCourse,
  useCourseStudents,
  useDeleteCourse,
  useDeleteLesson,
  useDeleteMaterial,
  useDeletePreview,
  useDeleteSection,
  useReorderLessons,
  useReorderSections,
  useUpdateCourse,
  useUpdateLesson,
  useUpdateSection,
  useUploadFile,
} from "@/hooks/use-courses";
import { ApiError } from "@/lib/api";
import type { AdminLesson, AdminSection } from "@/lib/types";

export default function CourseBuilderPage() {
  const params = useParams<{ id: string }>();
  const courseId = Number(params.id);
  const router = useRouter();

  const { data: course, isLoading, error, refetch } = useCourse(courseId);
  const { data: students } = useCourseStudents(courseId);
  const updateCourse = useUpdateCourse(courseId);
  const deleteCourse = useDeleteCourse();
  const deletePreview = useDeletePreview(courseId);
  const addSection = useAddSection(courseId);
  const updateSection = useUpdateSection(courseId);
  const deleteSection = useDeleteSection(courseId);
  const reorderSections = useReorderSections(courseId);
  const uploadFile = useUploadFile();

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [newSectionOpen, setNewSectionOpen] = useState(false);
  const coverInput = useRef<HTMLInputElement>(null);

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (error || !course) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل الكورس"} onRetry={() => refetch()} />;

  async function togglePublish() {
    try {
      await updateCourse.mutateAsync({ is_published: !course!.is_published });
      toast.success(course!.is_published ? "تم إلغاء نشر الكورس" : "تم نشر الكورس");
    } catch {
      // toast already shown globally
    }
  }

  async function saveSettings(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await updateCourse.mutateAsync({
        title: String(form.get("title") || "").trim(),
        subtitle: String(form.get("subtitle") || "").trim(),
        description: String(form.get("description") || "").trim(),
        subject: String(form.get("subject") || "").trim(),
        level: String(form.get("level") || "").trim(),
      });
      toast.success("تم حفظ بيانات الكورس");
    } catch {
      // toast already shown globally
    }
  }

  async function onCoverSelected(file: File) {
    try {
      const uploaded = await uploadFile.mutateAsync({ file, purpose: "course_cover" });
      await updateCourse.mutateAsync({ cover_file_id: uploaded.id });
      toast.success("تم تحديث صورة الغلاف");
    } catch {
      // toast already shown globally
    }
  }

  async function handleAddSection(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const title = String(new FormData(e.currentTarget).get("title") || "").trim();
    if (!title) return;
    try {
      await addSection.mutateAsync(title);
      setNewSectionOpen(false);
    } catch {
      // toast already shown globally
    }
  }

  async function moveSection(section: AdminSection, direction: -1 | 1) {
    const ids = course!.sections.map((s) => s.id);
    const idx = ids.indexOf(section.id);
    const swapWith = idx + direction;
    if (idx < 0 || swapWith < 0 || swapWith >= ids.length) return;
    const a = ids[idx] as number;
    const b = ids[swapWith] as number;
    ids[idx] = b;
    ids[swapWith] = a;
    try {
      await reorderSections.mutateAsync(ids);
    } catch {
      // toast already shown globally
    }
  }

  async function handleDelete(cascade: boolean) {
    try {
      await deleteCourse.mutateAsync({ id: courseId, cascade });
      toast.success(`تم حذف ${course!.title}`);
      router.push("/admin/courses");
    } catch {
      // toast already shown globally (also handles COURSE_HAS_DEPENDENTS as a normal error toast)
    }
  }

  return (
    <div className="talent-admin-page max-w-4xl">
      <Link href="/admin/courses" className="flex items-center gap-1.5 text-body-sm text-text-muted hover:text-text">
        <ArrowRight size={16} className="rtl-flip" /> رجوع للكورسات
      </Link>

      <header className="mt-3 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-6">
        <div>
          <h1 className="text-h1">{course.title}</h1>
          <div className="mt-2 flex items-center gap-2">
            <Badge tone={course.is_published ? "success" : "neutral"}>{course.is_published ? "منشور" : "مسودة"}</Badge>
            <span className="flex items-center gap-1 text-caption text-text-muted"><UsersRound size={14} /> {course.student_count} طالب</span>
            <span className="flex items-center gap-1 text-caption text-text-muted"><BookOpen size={14} /> {course.lesson_count} درس</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant={course.is_published ? "secondary" : "primary"} onClick={togglePublish} loading={updateCourse.isPending}>
            {course.is_published ? "إلغاء النشر" : "نشر الكورس"}
          </Button>
          <Button variant="danger" onClick={() => setConfirmDelete(true)}>
            <Trash2 size={16} /> حذف
          </Button>
        </div>
      </header>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>بيانات الكورس</CardTitle>
        </CardHeader>
        <div className="mb-4 flex items-center gap-4">
          <div className="relative flex size-20 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border bg-surface-2">
            {course.cover_url ? <Image src={course.cover_url} alt="" fill className="object-cover" unoptimized /> : <UploadCloud size={22} className="text-text-subtle" />}
          </div>
          <div>
            <Button variant="secondary" size="sm" onClick={() => coverInput.current?.click()} loading={uploadFile.isPending}>
              <UploadCloud size={15} /> {course.cover_url ? "تغيير الغلاف" : "رفع صورة غلاف"}
            </Button>
            <input ref={coverInput} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => e.target.files?.[0] && onCoverSelected(e.target.files[0])} />
            <p className="mt-1 text-caption">PNG / JPG / WebP — حتى 2 ميجابايت</p>
          </div>
        </div>
        <form onSubmit={saveSettings} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="title">اسم الكورس</Label>
              <Input id="title" name="title" required minLength={2} defaultValue={course.title} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="subject">المادة</Label>
              <Input id="subject" name="subject" required defaultValue={course.subject} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="subtitle">وصف مختصر</Label>
            <Input id="subtitle" name="subtitle" defaultValue={course.subtitle} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="level">المستوى</Label>
            <Input id="level" name="level" defaultValue={course.level} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="description">الوصف الكامل</Label>
            <Textarea id="description" name="description" rows={4} defaultValue={course.description} />
          </div>
          <Button size="sm" className="self-start" loading={updateCourse.isPending}>حفظ البيانات</Button>
        </form>
      </Card>

      <section className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-h2">محتوى الكورس</h2>
          <Button size="sm" onClick={() => setNewSectionOpen(true)}><Plus size={15} /> إضافة فصل</Button>
        </div>

        {course.sections.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border py-10 text-center text-body-sm text-text-muted">لا يوجد فصول بعد — أضف أول فصل لتبدأ إضافة الدروس.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {course.sections.map((section, index) => (
              <SectionCard
                key={section.id}
                courseId={courseId}
                section={section}
                isFirst={index === 0}
                isLast={index === course.sections.length - 1}
                onMove={(dir) => moveSection(section, dir)}
                onRename={(title) => updateSection.mutateAsync({ id: section.id, title })}
                onDelete={() => deleteSection.mutateAsync(section.id)}
              />
            ))}
          </div>
        )}
      </section>

      {students && students.length > 0 ? (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>الطلاب المشتركون</CardTitle>
            <CardDescription>{students.length} طالب لديهم وصول لهذا الكورس</CardDescription>
          </CardHeader>
          <div className="flex flex-col gap-2">
            {students.map((s) => (
              <div key={s.student_id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-body-sm">
                <span>{s.full_name}</span>
                <div className="flex items-center gap-2 text-caption text-text-muted">
                  <Badge tone={s.source === "direct" ? "primary" : "neutral"}>{s.source === "direct" ? "مباشر" : s.source_label}</Badge>
                  <span>{s.progress}%</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <Dialog open={newSectionOpen} onOpenChange={setNewSectionOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>إضافة فصل</DialogTitle>
            <DialogDescription>الفصول تنظّم الدروس داخل الكورس.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleAddSection} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="section-title">اسم الفصل</Label>
              <Input id="section-title" name="title" required minLength={2} placeholder="مثال: Algebra" autoFocus />
            </div>
            <Button loading={addSection.isPending}>إضافة</Button>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`حذف ${course.title}`}
        destructive
        loading={deleteCourse.isPending}
        confirmLabel={deletePreview.data && (deletePreview.data.exams || deletePreview.data.live_sessions) ? "حذف الكورس وكل ما يخصه" : "تأكيد الحذف"}
        onConfirm={() => handleDelete(true)}
        description={
          deletePreview.data ? (
            <span>
              سيتم حذف {deletePreview.data.sections} فصل، {deletePreview.data.lessons} درس، {deletePreview.data.materials} مرفق،{" "}
              {deletePreview.data.enrollments} اشتراك.
              {deletePreview.data.exams || deletePreview.data.live_sessions ? (
                <strong className="mt-2 block text-danger-fg">
                  تحذير: للكورس {deletePreview.data.exams} امتحان و{deletePreview.data.live_sessions} حصة لايف — هيتم حذفهم أيضًا.
                </strong>
              ) : null}
            </span>
          ) : "جارٍ التحميل..."
        }
      />
    </div>
  );
}

function SectionCard({
  courseId, section, isFirst, isLast, onMove, onRename, onDelete,
}: {
  courseId: number;
  section: AdminSection;
  isFirst: boolean;
  isLast: boolean;
  onMove: (dir: -1 | 1) => void;
  onRename: (title: string) => Promise<unknown>;
  onDelete: () => Promise<unknown>;
}) {
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [newLessonOpen, setNewLessonOpen] = useState(false);
  const addLesson = useAddLesson(courseId);
  const reorderLessons = useReorderLessons(courseId);

  async function saveRename(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const title = String(new FormData(e.currentTarget).get("title") || "").trim();
    if (title) await onRename(title);
    setEditing(false);
  }

  async function handleAddLesson(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      await addLesson.mutateAsync({
        sectionId: section.id,
        title: String(form.get("title") || "").trim(),
        duration_minutes: Number(form.get("duration_minutes") || 20),
        recording_url: String(form.get("recording_url") || "").trim() || null,
        is_preview: form.get("is_preview") === "on",
      });
      setNewLessonOpen(false);
    } catch {
      // toast already shown globally
    }
  }

  async function moveLesson(lesson: AdminLesson, direction: -1 | 1) {
    const ids = section.lessons.map((l) => l.id);
    const idx = ids.indexOf(lesson.id);
    const swapWith = idx + direction;
    if (idx < 0 || swapWith < 0 || swapWith >= ids.length) return;
    const a = ids[idx] as number;
    const b = ids[swapWith] as number;
    ids[idx] = b;
    ids[swapWith] = a;
    await reorderLessons.mutateAsync({ sectionId: section.id, ids });
  }

  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        {editing ? (
          <form onSubmit={saveRename} className="flex flex-1 items-center gap-2">
            <Input name="title" defaultValue={section.title} autoFocus className="h-9" />
            <Button size="sm" type="submit">حفظ</Button>
            <Button size="sm" variant="ghost" type="button" onClick={() => setEditing(false)}>إلغاء</Button>
          </form>
        ) : (
          <button className="text-h3 hover:text-primary" onClick={() => setEditing(true)}>{section.title}</button>
        )}
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" disabled={isFirst} onClick={() => onMove(-1)} aria-label="نقل لأعلى"><ChevronUp size={16} /></Button>
          <Button variant="ghost" size="icon" disabled={isLast} onClick={() => onMove(1)} aria-label="نقل لأسفل"><ChevronDown size={16} /></Button>
          <Button variant="ghost" size="icon" onClick={() => setConfirmDelete(true)} aria-label="حذف الفصل"><Trash2 size={16} className="text-danger-fg" /></Button>
        </div>
      </div>

      <div className="mt-3 flex flex-col gap-2">
        {section.lessons.map((lesson, index) => (
          <LessonRow
            key={lesson.id}
            courseId={courseId}
            lesson={lesson}
            isFirst={index === 0}
            isLast={index === section.lessons.length - 1}
            onMove={(dir) => moveLesson(lesson, dir)}
          />
        ))}
        <Button variant="secondary" size="sm" className="self-start" onClick={() => setNewLessonOpen(true)}>
          <Plus size={15} /> إضافة درس
        </Button>
      </div>

      <Dialog open={newLessonOpen} onOpenChange={setNewLessonOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>إضافة درس إلى {section.title}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddLesson} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="lesson-title">اسم الدرس</Label>
              <Input id="lesson-title" name="title" required minLength={2} autoFocus />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="duration">مدة الدرس (دقيقة)</Label>
              <Input id="duration" name="duration_minutes" type="number" min={1} max={600} defaultValue={20} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="recording_url">رابط التسجيل (اختياري)</Label>
              <Input id="recording_url" name="recording_url" dir="ltr" placeholder="https://youtube.com/..." />
            </div>
            <label className="flex items-center gap-2 text-body-sm">
              <input type="checkbox" name="is_preview" className="size-4 rounded border-border" />
              درس تعريفي (متاح للمعاينة)
            </label>
            <Button loading={addLesson.isPending}>إضافة الدرس</Button>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`حذف فصل ${section.title}`}
        destructive
        onConfirm={async () => { await onDelete(); setConfirmDelete(false); }}
        description={`سيتم حذف ${section.lessons.length} درس بداخل هذا الفصل.`}
      />
    </Card>
  );
}

function LessonRow({ courseId, lesson, isFirst, isLast, onMove }: { courseId: number; lesson: AdminLesson; isFirst: boolean; isLast: boolean; onMove: (dir: -1 | 1) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [materialOpen, setMaterialOpen] = useState(false);
  const [materialMode, setMaterialMode] = useState<"link" | "upload">("link");
  const deleteLesson = useDeleteLesson(courseId);
  const addMaterial = useAddMaterial(courseId);
  const deleteMaterial = useDeleteMaterial(courseId);
  const uploadFile = useUploadFile();
  const updateLesson = useUpdateLesson(courseId);

  async function handleAddMaterial(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const title = String(form.get("title") || "").trim();
    try {
      if (materialMode === "link") {
        await addMaterial.mutateAsync({ lessonId: lesson.id, title, material_type: "link", url: String(form.get("url") || "").trim() });
      } else {
        const fileInput = form.get("file") as File;
        if (!fileInput || fileInput.size === 0) return;
        const uploaded = await uploadFile.mutateAsync({ file: fileInput, purpose: "material_pdf" });
        await addMaterial.mutateAsync({ lessonId: lesson.id, title, material_type: "file", file_id: uploaded.id });
      }
      setMaterialOpen(false);
    } catch {
      // toast already shown globally
    }
  }

  return (
    <div className="rounded-md border border-border">
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <button className="flex flex-1 items-center gap-2 text-start text-body-sm" onClick={() => setExpanded((v) => !v)}>
          <ChevronDown size={15} className={`transition-transform ${expanded ? "" : "-rotate-90"}`} />
          {lesson.title}
          {lesson.is_preview ? <Badge tone="info">تعريفي</Badge> : null}
          <span className="text-caption text-text-subtle">{lesson.materials.length} مرفق</span>
        </button>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" disabled={isFirst} onClick={() => onMove(-1)} aria-label="نقل لأعلى"><ChevronUp size={14} /></Button>
          <Button variant="ghost" size="icon" disabled={isLast} onClick={() => onMove(1)} aria-label="نقل لأسفل"><ChevronDown size={14} /></Button>
          <Button variant="ghost" size="icon" onClick={() => setConfirmDelete(true)} aria-label="حذف الدرس"><Trash2 size={14} className="text-danger-fg" /></Button>
        </div>
      </div>

      {expanded ? (
        <div className="border-t border-border px-3 py-3">
          <label className="flex items-center gap-2 text-body-sm">
            <input
              type="checkbox"
              checked={lesson.is_preview}
              onChange={(e) => updateLesson.mutate({ id: lesson.id, is_preview: e.target.checked })}
              className="size-4 rounded border-border"
            />
            درس تعريفي
          </label>

          <div className="mt-3 flex flex-col gap-1.5">
            {lesson.materials.map((m) => (
              <div key={m.id} className="flex items-center justify-between rounded-md bg-surface-2 px-3 py-1.5 text-body-sm">
                <span className="flex items-center gap-1.5">
                  {m.material_type === "file" ? <FileText size={14} /> : <LinkIcon size={14} />} {m.title}
                </span>
                <button onClick={() => deleteMaterial.mutate(m.id)} className="text-text-subtle hover:text-danger-fg" aria-label="حذف المرفق"><Trash2 size={13} /></button>
              </div>
            ))}
            <Button variant="ghost" size="sm" className="self-start" onClick={() => setMaterialOpen(true)}><Plus size={14} /> إضافة مرفق</Button>
          </div>
        </div>
      ) : null}

      <Dialog open={materialOpen} onOpenChange={setMaterialOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>إضافة مرفق لـ {lesson.title}</DialogTitle>
          </DialogHeader>
          <div className="mb-3 flex gap-2">
            <Button size="sm" variant={materialMode === "link" ? "primary" : "secondary"} type="button" onClick={() => setMaterialMode("link")}>رابط خارجي</Button>
            <Button size="sm" variant={materialMode === "upload" ? "primary" : "secondary"} type="button" onClick={() => setMaterialMode("upload")}>رفع PDF</Button>
          </div>
          <form onSubmit={handleAddMaterial} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="material-title">اسم المرفق</Label>
              <Input id="material-title" name="title" required minLength={2} />
            </div>
            {materialMode === "link" ? (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="material-url">الرابط</Label>
                <Input id="material-url" name="url" dir="ltr" required placeholder="https://..." />
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="material-file">ملف PDF (حتى 20 ميجابايت)</Label>
                <input id="material-file" name="file" type="file" accept="application/pdf" required className="text-body-sm" />
              </div>
            )}
            <Button loading={addMaterial.isPending || uploadFile.isPending}>إضافة</Button>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`حذف درس ${lesson.title}`}
        destructive
        onConfirm={async () => { await deleteLesson.mutateAsync(lesson.id); setConfirmDelete(false); }}
        description="سيتم حذف الدرس وكل مرفقاته."
      />
    </div>
  );
}
