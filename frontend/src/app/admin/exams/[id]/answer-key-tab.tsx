"use client";

import { AlertTriangle, CheckCircle2, Lock } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useApplyAnswerKey, usePreviewAnswerKey } from "@/hooks/use-exams";
import { ApiError } from "@/lib/api";
import type { AdminExamDetail } from "@/lib/types";

export function AnswerKeyTab({ exam }: { exam: AdminExamDetail }) {
  const locked = exam.has_attempts;
  const [text, setText] = useState("");
  const preview = usePreviewAnswerKey(exam.id);
  const applyKey = useApplyAnswerKey(exam.id);

  useEffect(() => {
    if (!text.trim()) return;
    const timer = setTimeout(() => preview.mutate(text), 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (locked) return;
    const form = new FormData(e.currentTarget);
    const pointsRaw = String(form.get("points_per_question") || "").trim();
    try {
      await applyKey.mutateAsync({
        answers: text,
        points_per_question: pointsRaw ? Number(pointsRaw) : null,
        publish: form.get("publish") === "on",
      });
      toast.success("تم حفظ مفتاح الإجابة");
    } catch {
      // surfaced via applyKey.error below
    }
  }

  const result = preview.data;

  return (
    <div className="max-w-2xl">
      {locked ? (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-info-soft px-4 py-3 text-body-sm text-info-fg">
          <Lock size={16} /> مفتاح الإجابة مجمّد — بدأ طلاب في أداء هذا الامتحان.
        </div>
      ) : null}

      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="answers">مفتاح الإجابة</Label>
          <textarea
            id="answers"
            dir="ltr"
            rows={8}
            value={text}
            disabled={locked}
            onChange={(e) => setText(e.target.value)}
            placeholder={"BCAD\nأو\n1-B 2-C 3-A 4-D"}
            className="rounded-md border border-border bg-surface p-3 font-mono text-body-sm ltr disabled:opacity-50"
          />
          <p className="text-caption text-text-subtle">صيغ مقبولة: BCAD — B C A D — بفواصل أو أسطر جديدة — 1-B 2-C — 1)B — 1.B — 1:B</p>
        </div>

        {text.trim() ? (
          <div className={`rounded-md px-4 py-3 text-body-sm ${result?.errors.length ? "bg-danger-soft text-danger-fg" : "bg-success-soft text-success-fg"}`}>
            {preview.isPending ? (
              "جارٍ التحليل..."
            ) : result?.errors.length ? (
              <div className="flex items-start gap-2"><AlertTriangle size={16} className="mt-0.5 shrink-0" /> <span>{result.errors.join("، ")}</span></div>
            ) : result ? (
              <div className="flex items-center gap-2">
                <CheckCircle2 size={16} />
                <span>تم التعرف على {result.count} إجابة{result.question_count ? ` مقابل ${result.question_count} سؤال حالي` : ""}</span>
              </div>
            ) : null}
            {result && result.parsed.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1 ltr">
                {result.parsed.map((letter, i) => <Badge key={i} tone="neutral">{i + 1}. {letter}</Badge>)}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="flex flex-col gap-1.5 max-w-[220px]">
          <Label htmlFor="points_per_question">نقاط كل سؤال (اختياري)</Label>
          <Input id="points_per_question" name="points_per_question" type="number" min={0} max={100} disabled={locked} placeholder="اتركه فارغًا للإبقاء على القيم الحالية" />
        </div>

        <label className="flex items-center gap-2 text-body-sm">
          <input type="checkbox" name="publish" defaultChecked disabled={locked} className="size-4 rounded border-border" />
          نشر الامتحان بعد الحفظ
        </label>

        {applyKey.error ? <p className="rounded-md bg-danger-soft px-3.5 py-2.5 text-body-sm text-danger-fg">{(applyKey.error as ApiError).message}</p> : null}

        <Button loading={applyKey.isPending} disabled={locked || !text.trim() || !!result?.errors.length} className="self-start">
          حفظ مفتاح الإجابة
        </Button>
      </form>
    </div>
  );
}
