"use client";

import Image from "next/image";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, FileImage, Plus, Trash2, UploadCloud } from "lucide-react";
import { FormEvent, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Label } from "@/components/ui/input";
import { useAddTextQuestion, useDeleteQuestion, useReorderQuestions, useUpdateQuestion, useUploadQuestionImages } from "@/hooks/use-exams";
import { ApiError } from "@/lib/api";
import { compressImageToWebp } from "@/lib/image-compress";
import type { AdminExamDetail, ChoiceLabel, ExamQuestionOut } from "@/lib/types";

const BATCH_SIZE = 10;
const LABELS: ChoiceLabel[] = ["A", "B", "C", "D"];

export function QuestionsTab({ exam }: { exam: AdminExamDetail }) {
  const locked = exam.has_attempts;
  const [manualOpen, setManualOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [batchProgress, setBatchProgress] = useState<{ done: number; total: number } | null>(null);
  const [batchErrors, setBatchErrors] = useState<string[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  const uploadImages = useUploadQuestionImages(exam.id);
  const reorderQuestions = useReorderQuestions(exam.id);

  const questions = [...exam.questions].sort((a, b) => a.position - b.position);

  async function handleFiles(files: FileList | File[]) {
    if (locked) return;
    const list = Array.from(files).filter((f) => f.type.startsWith("image/"));
    if (list.length === 0) return;

    setBatchErrors([]);
    setBatchProgress({ done: 0, total: list.length });
    const batches: File[][] = [];
    for (let i = 0; i < list.length; i += BATCH_SIZE) batches.push(list.slice(i, i + BATCH_SIZE));

    let done = 0;
    for (const batch of batches) {
      try {
        const compressed = await Promise.all(batch.map((f) => compressImageToWebp(f).catch(() => f)));
        await uploadImages.mutateAsync({ files: compressed, topic: "General", difficulty: "medium", points: 1 });
        done += batch.length;
        setBatchProgress({ done, total: list.length });
      } catch (err) {
        setBatchErrors((prev) => [...prev, err instanceof ApiError ? err.message : "فشل رفع مجموعة من الصور"]);
        done += batch.length;
        setBatchProgress({ done, total: list.length });
      }
    }
    if (fileInput.current) fileInput.current.value = "";
    setTimeout(() => setBatchProgress(null), 1500);
  }

  async function moveQuestion(question: ExamQuestionOut, direction: -1 | 1) {
    const ids = questions.map((q) => q.id);
    const idx = ids.indexOf(question.id);
    const swapWith = idx + direction;
    if (idx < 0 || swapWith < 0 || swapWith >= ids.length) return;
    const a = ids[idx] as number;
    const b = ids[swapWith] as number;
    ids[idx] = b;
    ids[swapWith] = a;
    try {
      await reorderQuestions.mutateAsync(ids);
    } catch {
      // toast already shown globally
    }
  }

  return (
    <div>
      {!locked ? (
        <div className="flex flex-col gap-3">
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
            onClick={() => fileInput.current?.click()}
            className={`flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${dragging ? "border-primary bg-primary-soft" : "border-border hover:bg-surface-2"}`}
          >
            <UploadCloud size={28} className="text-primary" />
            <p className="text-body-sm">اسحب صور الأسئلة هنا أو اضغط للاختيار</p>
            <p className="text-caption text-text-subtle">WebP / PNG / JPEG — تُضغط تلقائيًا لأقل من 800 كيلوبايت، وتُرفع بحد أقصى 10 لكل دفعة</p>
            <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp" multiple className="hidden" onChange={(e) => e.target.files && handleFiles(e.target.files)} />
          </div>

          {batchProgress ? (
            <div className="flex items-center gap-2 rounded-md bg-primary-soft px-4 py-2.5 text-body-sm text-primary-soft-fg">
              <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
              جاري رفع {batchProgress.done}/{batchProgress.total} صورة...
            </div>
          ) : null}
          {batchErrors.map((err, i) => (
            <p key={i} className="rounded-md bg-danger-soft px-4 py-2.5 text-body-sm text-danger-fg">{err}</p>
          ))}

          <Button variant="secondary" size="sm" className="self-start" onClick={() => setManualOpen(true)}>
            <Plus size={15} /> إضافة سؤال نصي يدويًا
          </Button>
        </div>
      ) : null}

      {questions.length === 0 ? (
        <p className="mt-6 rounded-lg border border-dashed border-border py-10 text-center text-body-sm text-text-muted">لا يوجد أسئلة بعد.</p>
      ) : (
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {questions.map((question, index) => (
            <QuestionCard
              key={question.id}
              examId={exam.id}
              question={question}
              locked={locked}
              isFirst={index === 0}
              isLast={index === questions.length - 1}
              onMove={(dir) => moveQuestion(question, dir)}
            />
          ))}
        </div>
      )}

      <Dialog open={manualOpen} onOpenChange={setManualOpen}>
        <ManualQuestionForm examId={exam.id} onDone={() => setManualOpen(false)} />
      </Dialog>
    </div>
  );
}

function QuestionCard({ examId, question, locked, isFirst, isLast, onMove }: {
  examId: number; question: ExamQuestionOut; locked: boolean; isFirst: boolean; isLast: boolean; onMove: (dir: -1 | 1) => void;
}) {
  const updateQuestion = useUpdateQuestion(examId);
  const deleteQuestion = useDeleteQuestion(examId);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const correctChoice = question.choices.find((c) => c.is_correct);
  const hasCorrect = !!correctChoice;

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border bg-surface">
      <div className="relative flex aspect-video items-center justify-center bg-surface-2">
        {question.image_url ? (
          <Image src={question.image_url} alt="" fill className="object-contain" unoptimized />
        ) : (
          <div className="flex flex-col items-center gap-1 p-3 text-center">
            <FileImage size={20} className="text-text-subtle" />
            <p className="line-clamp-3 text-body-sm">{question.prompt_text || "بدون نص"}</p>
          </div>
        )}
        <span className="absolute start-2 top-2 flex size-7 items-center justify-center rounded-full bg-surface-raised text-caption font-bold shadow-[var(--shadow-1)]">
          {question.position}
        </span>
        <span className={`absolute end-2 top-2 flex size-7 items-center justify-center rounded-full text-caption font-bold ${hasCorrect ? "bg-success-soft text-success-fg" : "bg-danger-soft text-danger-fg"}`}>
          {correctChoice?.label ?? <AlertTriangle size={13} />}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <div className="flex items-center gap-1.5">
          <select
            value={question.topic}
            onChange={(e) => updateQuestion.mutate({ id: question.id, topic: e.target.value })}
            className="h-8 flex-1 rounded-md border border-border bg-surface px-2 text-caption"
          >
            <option value={question.topic}>{question.topic}</option>
            {["General", "Algebra", "Geometry", "Grammar", "Reading", "Science"].filter((t) => t !== question.topic).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-1.5">
          <select
            value={question.difficulty}
            onChange={(e) => updateQuestion.mutate({ id: question.id, difficulty: e.target.value as "easy" | "medium" | "hard" })}
            disabled={locked}
            className="h-8 rounded-md border border-border bg-surface px-2 text-caption disabled:opacity-50"
          >
            <option value="easy">سهل</option>
            <option value="medium">متوسط</option>
            <option value="hard">صعب</option>
          </select>
          <Input
            type="number" min={0} max={100} defaultValue={question.points} disabled={locked}
            onBlur={(e) => { const v = Number(e.target.value); if (v !== question.points) updateQuestion.mutate({ id: question.id, points: v }); }}
            className="h-8 w-16 px-2 text-caption"
          />
          <span className="text-caption text-text-subtle">نقطة</span>
        </div>
        <div className="mt-auto flex items-center justify-between">
          <div className="flex items-center gap-0.5">
            <Button variant="ghost" size="icon" className="size-7" disabled={isFirst} onClick={() => onMove(-1)} aria-label="نقل لأعلى"><ChevronUp size={14} /></Button>
            <Button variant="ghost" size="icon" className="size-7" disabled={isLast} onClick={() => onMove(1)} aria-label="نقل لأسفل"><ChevronDown size={14} /></Button>
          </div>
          <Button variant="ghost" size="icon" className="size-7" disabled={locked} onClick={() => setConfirmDelete(true)} aria-label="حذف"><Trash2 size={14} className="text-danger-fg" /></Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`حذف السؤال ${question.position}`}
        destructive
        loading={deleteQuestion.isPending}
        onConfirm={async () => { await deleteQuestion.mutateAsync(question.id); setConfirmDelete(false); }}
        description="لا يمكن التراجع عن هذا الإجراء."
      />
    </div>
  );
}

function ManualQuestionForm({ examId, onDone }: { examId: number; onDone: () => void }) {
  const create = useAddTextQuestion(examId);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const correct = String(form.get("correct_label") || "A") as ChoiceLabel;
    try {
      await create.mutateAsync({
        question_type: "text_mcq",
        prompt_text: String(form.get("prompt_text") || "").trim(),
        choices: LABELS.map((label) => ({ label, text: String(form.get(`choice_${label}`) || "").trim() })),
        correct_label: correct,
        topic: String(form.get("topic") || "General").trim(),
        difficulty: String(form.get("difficulty") || "medium") as "easy" | "medium" | "hard",
        points: Number(form.get("points") || 1),
      });
      toast.success("تم إضافة السؤال");
      onDone();
    } catch {
      // surfaced via create.error below
    }
  }

  return (
    <DialogContent side="end">
      <DialogHeader>
        <DialogTitle>إضافة سؤال نصي</DialogTitle>
        <DialogDescription>أدخل نص السؤال والاختيارات الأربعة، وحدد الإجابة الصحيحة.</DialogDescription>
      </DialogHeader>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="prompt_text">نص السؤال</Label>
          <Input id="prompt_text" name="prompt_text" required minLength={1} autoFocus />
        </div>
        {LABELS.map((label) => (
          <div key={label} className="flex flex-col gap-1.5">
            <Label htmlFor={`choice_${label}`}>اختيار {label}</Label>
            <Input id={`choice_${label}`} name={`choice_${label}`} required />
          </div>
        ))}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="correct_label">الإجابة الصحيحة</Label>
          <select id="correct_label" name="correct_label" defaultValue="A" className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            {LABELS.map((label) => <option key={label} value={label}>{label}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="topic">الموضوع</Label>
            <Input id="topic" name="topic" defaultValue="General" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="points">النقاط</Label>
            <Input id="points" name="points" type="number" min={0} max={100} defaultValue={1} />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="difficulty">الصعوبة</Label>
          <select id="difficulty" name="difficulty" defaultValue="medium" className="h-11 rounded-md border border-border bg-surface px-3 text-body-sm">
            <option value="easy">سهل</option>
            <option value="medium">متوسط</option>
            <option value="hard">صعب</option>
          </select>
        </div>
        {create.error ? <p className="text-body-sm text-danger-fg">{(create.error as ApiError).message}</p> : null}
        <Button loading={create.isPending}>إضافة السؤال</Button>
      </form>
    </DialogContent>
  );
}
