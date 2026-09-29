"use client";

import Image from "next/image";
import { BookOpen, ChevronDown, ChevronUp, FileImage, Link2, Plus, Trash2, UploadCloud } from "lucide-react";
import { FormEvent, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Label, Textarea } from "@/components/ui/input";
import {
  useCreatePassage,
  useDeletePassage,
  useReorderPassages,
  useSetPassageQuestions,
  useUpdatePassage,
  useUploadPassageImage,
} from "@/hooks/use-exams";
import { ApiError } from "@/lib/api";
import { compressImageToWebp } from "@/lib/image-compress";
import type { AdminExamDetail, ExamPassageOut } from "@/lib/types";

export function PassagesTab({ exam }: { exam: AdminExamDetail }) {
  const [createOpen, setCreateOpen] = useState(false);
  const reorderPassages = useReorderPassages(exam.id);
  const passages = [...exam.passages].sort((a, b) => a.position - b.position);

  async function movePassage(passage: ExamPassageOut, direction: -1 | 1) {
    const ids = passages.map((p) => p.id);
    const idx = ids.indexOf(passage.id);
    const swapWith = idx + direction;
    if (idx < 0 || swapWith < 0 || swapWith >= ids.length) return;
    const a = ids[idx] as number;
    const b = ids[swapWith] as number;
    ids[idx] = b;
    ids[swapWith] = a;
    try {
      await reorderPassages.mutateAsync(ids);
    } catch {
      // toast already shown globally
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-body-sm text-text-muted">مقاطع قراءة اختيارية يمكن ربط أسئلة الامتحان بها — تظهر للطالب جنب السؤال أثناء الامتحان.</p>
        <Button size="sm" onClick={() => setCreateOpen(true)}><Plus size={15} /> إضافة مقطع</Button>
      </div>

      {passages.length === 0 ? (
        <EmptyState className="mt-6" icon={BookOpen} title="لا يوجد مقاطع بعد" description="أضف مقطع قراءة واربط به أسئلة الامتحان." />
      ) : (
        <div className="mt-6 flex flex-col gap-4">
          {passages.map((passage, index) => (
            <PassageCard
              key={passage.id}
              exam={exam}
              passage={passage}
              isFirst={index === 0}
              isLast={index === passages.length - 1}
              onMove={(dir) => movePassage(passage, dir)}
            />
          ))}
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <PassageForm examId={exam.id} onDone={() => setCreateOpen(false)} />
      </Dialog>
    </div>
  );
}

function PassageCard({ exam, passage, isFirst, isLast, onMove }: {
  exam: AdminExamDetail; passage: ExamPassageOut; isFirst: boolean; isLast: boolean; onMove: (dir: -1 | 1) => void;
}) {
  const deletePassage = useDeletePassage(exam.id);
  const uploadImage = useUploadPassageImage(exam.id);
  const [editOpen, setEditOpen] = useState(false);
  const [questionsOpen, setQuestionsOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  async function handleImage(file: File) {
    try {
      const compressed = await compressImageToWebp(file).catch(() => file);
      await uploadImage.mutateAsync({ id: passage.id, file: compressed });
      toast.success("تم رفع صورة المقطع");
    } catch {
      // toast already shown globally
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  const linkedQuestions = exam.questions.filter((q) => passage.question_ids.includes(q.id)).sort((a, b) => a.position - b.position);

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 sm:flex-row">
      <div className="relative flex h-32 w-full shrink-0 items-center justify-center overflow-hidden rounded-md bg-surface-2 sm:w-48">
        {passage.image_url ? (
          <Image src={passage.image_url} alt="" fill className="object-cover" unoptimized />
        ) : (
          <FileImage size={24} className="text-text-subtle" />
        )}
        <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => e.target.files?.[0] && handleImage(e.target.files[0])} />
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="absolute inset-x-2 bottom-2 flex items-center justify-center gap-1 rounded-md bg-surface-raised/90 py-1.5 text-caption font-medium shadow-[var(--shadow-1)]"
        >
          <UploadCloud size={13} /> {passage.image_url ? "تغيير الصورة" : "رفع صورة"}
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <span className="text-caption text-text-subtle">مقطع {passage.position}</span>
            <h4 className="text-h3">{passage.title || "بدون عنوان"}</h4>
          </div>
          <div className="flex items-center gap-0.5">
            <Button variant="ghost" size="icon" className="size-7" disabled={isFirst} onClick={() => onMove(-1)} aria-label="نقل لأعلى"><ChevronUp size={14} /></Button>
            <Button variant="ghost" size="icon" className="size-7" disabled={isLast} onClick={() => onMove(1)} aria-label="نقل لأسفل"><ChevronDown size={14} /></Button>
          </div>
        </div>
        <p className="line-clamp-2 text-body-sm text-text-muted">{passage.body_text || "بدون نص"}</p>

        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <Badge tone={linkedQuestions.length > 0 ? "primary" : "neutral"}>
            <Link2 size={12} /> {linkedQuestions.length} سؤال مرتبط
          </Badge>
          {linkedQuestions.map((q) => <Badge key={q.id} tone="neutral">سؤال {q.position}</Badge>)}
        </div>

        <div className="mt-auto flex items-center gap-2 pt-2">
          <Button variant="secondary" size="sm" onClick={() => setEditOpen(true)}>تعديل النص</Button>
          <Button variant="secondary" size="sm" onClick={() => setQuestionsOpen(true)}>ربط الأسئلة</Button>
          <Button variant="ghost" size="icon" className="size-8" onClick={() => setConfirmDelete(true)} aria-label="حذف المقطع"><Trash2 size={15} className="text-danger-fg" /></Button>
        </div>
      </div>

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <PassageForm examId={exam.id} passage={passage} onDone={() => setEditOpen(false)} />
      </Dialog>
      <Dialog open={questionsOpen} onOpenChange={setQuestionsOpen}>
        <PassageQuestionsForm exam={exam} passage={passage} onDone={() => setQuestionsOpen(false)} />
      </Dialog>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`حذف مقطع "${passage.title || passage.position}"`}
        destructive
        loading={deletePassage.isPending}
        onConfirm={async () => {
          try {
            await deletePassage.mutateAsync(passage.id);
            setConfirmDelete(false);
            toast.success("تم حذف المقطع");
          } catch {
            // The global mutation handler shows the backend's message. Keep the dialog open so
            // the admin can retry instead of leaking an unhandled rejected promise.
          }
        }}
        description="الأسئلة المرتبطة بهذا المقطع لن تُحذف، لكنها ستفقد ارتباطها به."
      />
    </div>
  );
}

function PassageForm({ examId, passage, onDone }: { examId: number; passage?: ExamPassageOut; onDone: () => void }) {
  const create = useCreatePassage(examId);
  const update = useUpdatePassage(examId);
  const mutation = passage ? update : create;

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload = { title: String(form.get("title") || "").trim(), body_text: String(form.get("body_text") || "").trim() };
    try {
      if (passage) await update.mutateAsync({ id: passage.id, ...payload });
      else await create.mutateAsync(payload);
      toast.success(passage ? "تم حفظ المقطع" : "تم إضافة المقطع");
      onDone();
    } catch {
      // surfaced via mutation.error below
    }
  }

  return (
    <DialogContent side="end">
      <DialogHeader>
        <DialogTitle>{passage ? "تعديل المقطع" : "إضافة مقطع قراءة"}</DialogTitle>
        <DialogDescription>العنوان اختياري؛ النص يظهر للطالب جنب الأسئلة المرتبطة أثناء الامتحان.</DialogDescription>
      </DialogHeader>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="title">العنوان (اختياري)</Label>
          <Input id="title" name="title" defaultValue={passage?.title} autoFocus />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="body_text">نص المقطع</Label>
          <Textarea id="body_text" name="body_text" rows={10} defaultValue={passage?.body_text} />
        </div>
        {mutation.error ? <p className="text-body-sm text-danger-fg">{(mutation.error as ApiError).message}</p> : null}
        <Button loading={mutation.isPending}>{passage ? "حفظ" : "إضافة"}</Button>
      </form>
    </DialogContent>
  );
}

function PassageQuestionsForm({ exam, passage, onDone }: { exam: AdminExamDetail; passage: ExamPassageOut; onDone: () => void }) {
  const setQuestions = useSetPassageQuestions(exam.id);
  const [selected, setSelected] = useState<Set<number>>(new Set(passage.question_ids));
  const questions = [...exam.questions].sort((a, b) => a.position - b.position);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit() {
    try {
      await setQuestions.mutateAsync({ id: passage.id, questionIds: Array.from(selected) });
      toast.success("تم تحديث أسئلة المقطع");
      onDone();
    } catch {
      // toast already shown globally
    }
  }

  return (
    <DialogContent>
      <DialogHeader>
        <DialogTitle>ربط الأسئلة بالمقطع</DialogTitle>
        <DialogDescription>اختر أسئلة هذا الامتحان التي تنتمي لهذا المقطع. السؤال المرتبط بمقطع آخر سيُنقل لهذا المقطع.</DialogDescription>
      </DialogHeader>
      <div className="flex max-h-96 flex-col gap-2 overflow-y-auto">
        {questions.length === 0 ? (
          <p className="py-6 text-center text-body-sm text-text-muted">لا يوجد أسئلة في هذا الامتحان بعد.</p>
        ) : (
          questions.map((q) => {
            const otherPassage = q.passage_id && q.passage_id !== passage.id ? exam.passages.find((p) => p.id === q.passage_id) : null;
            return (
              <label key={q.id} className="flex cursor-pointer items-start gap-3 rounded-md border border-border p-2.5 hover:bg-surface-2">
                <Checkbox checked={selected.has(q.id)} onCheckedChange={() => toggle(q.id)} className="mt-0.5" />
                <span className="flex-1 text-body-sm">
                  <strong>سؤال {q.position}</strong> — {q.prompt_text || "(بدون نص، صورة فقط)"}
                  {otherPassage ? <span className="mt-1 block text-caption text-warning-fg">مرتبط حاليًا بمقطع &quot;{otherPassage.title || otherPassage.position}&quot;</span> : null}
                </span>
              </label>
            );
          })
        )}
      </div>
      {setQuestions.error ? <p className="text-body-sm text-danger-fg">{(setQuestions.error as ApiError).message}</p> : null}
      <Button className="mt-2" loading={setQuestions.isPending} onClick={submit}>حفظ الربط</Button>
    </DialogContent>
  );
}
