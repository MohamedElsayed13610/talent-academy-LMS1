"use client";

import Image from "next/image";
import { useRouter, useParams } from "next/navigation";
import {
  AlertTriangle, BookOpen, CheckCircle2, ChevronDown, ChevronUp, Clock, Expand, Lock, Trophy,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useAttempt, useAutosaveAnswers, useReportViolation, useSubmitAttempt } from "@/hooks/use-student-exams";
import { ApiError } from "@/lib/api";
import type { AnswerIn, AttemptPassageOut, AttemptPayload, AttemptQuestionOut, ExamResult, ViolationType } from "@/lib/types";

export default function ExamAttemptPage() {
  const params = useParams<{ attemptId: string }>();
  const attemptId = Number(params.attemptId);
  const { data, isLoading, error, refetch } = useAttempt(attemptId);

  if (isLoading) return <Skeleton className="h-[70vh] w-full" />;
  if (error || !data) return <ErrorState message={error instanceof ApiError ? error.message : "تعذر تحميل المحاولة"} onRetry={() => refetch()} />;

  if (data.status === "locked") return <LockedScreen violationCount={data.violation_count} violationLimit={data.violation_limit} />;
  if (data.status === "submitted" || data.status === "expired") return <ClosedScreen status={data.status} />;

  return <ActiveRunner attemptId={attemptId} initial={data} />;
}

// ------------------------------------------------------------------------------ closed states ----

function BackToExams() {
  const router = useRouter();
  return <Button className="mt-4" onClick={() => router.push("/exams")}>الامتحانات</Button>;
}

function LockedScreen({ violationCount, violationLimit }: { violationCount: number; violationLimit: number }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 rounded-lg border border-danger-soft bg-danger-soft py-14 px-6 text-center">
      <Lock size={28} className="text-danger-fg" />
      <h2 className="text-h3">المحاولة مقفلة</h2>
      <p className="text-body-sm text-danger-fg">
        تم قفل هذه المحاولة بعد {violationCount} من {violationLimit} مخالفات مسموحة (مغادرة الصفحة أو تبديل النافذة). تواصل مع الإدارة لإعادة فتحها.
      </p>
      <BackToExams />
    </div>
  );
}

function ClosedScreen({ status }: { status: "submitted" | "expired" }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 rounded-lg border border-border bg-surface-2 py-14 px-6 text-center">
      <CheckCircle2 size={28} className="text-text-muted" />
      <h2 className="text-h3">{status === "submitted" ? "تم تسليم هذه المحاولة من قبل" : "انتهى وقت هذه المحاولة"}</h2>
      <p className="text-body-sm text-text-muted">النتيجة متاحة في صفحة الامتحان.</p>
      <BackToExams />
    </div>
  );
}

function ResultScreen({ result }: { result: ExamResult }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 rounded-lg border border-border bg-surface py-14 px-6 text-center shadow-[var(--shadow-1)]">
      {result.passed ? <Trophy size={32} className="text-accent-fg" /> : <AlertTriangle size={32} className="text-warning-fg" />}
      <div>
        <h2 className="text-h1">{result.percentage}%</h2>
        <p className="mt-1 text-body-sm text-text-muted">{result.score_points} من {result.total_points} نقطة</p>
      </div>
      <Badge tone={result.passed ? "success" : "danger"}>{result.passed ? "ناجح" : "غير ناجح"}</Badge>
      {result.points_awarded > 0 ? (
        <p className="text-body-sm">حصلت على <strong>{result.points_awarded}</strong> نقطة إضافية.</p>
      ) : null}
      <BackToExams />
    </div>
  );
}

// -------------------------------------------------------------------------------- active runner ----

function toAnswerList(answers: Record<number, number | null>): AnswerIn[] {
  return Object.entries(answers).map(([questionId, choiceId]) => ({ question_id: Number(questionId), choice_id: choiceId }));
}

function ActiveRunner({ attemptId, initial }: { attemptId: number; initial: AttemptPayload }) {
  const autosave = useAutosaveAnswers(attemptId);
  const submitAttempt = useSubmitAttempt(attemptId);
  const reportViolationMutation = useReportViolation(attemptId);

  const questions = [...initial.questions].sort((a, b) => a.position - b.position);
  const passageById = new Map(initial.passages.map((p) => [p.id, p]));

  const [answers, setAnswers] = useState<Record<number, number | null>>(() => {
    const map: Record<number, number | null> = {};
    for (const q of questions) map[q.id] = initial.saved_answers[q.id] ?? null;
    return map;
  });
  const [currentIndex, setCurrentIndex] = useState(0);
  const [violationCount, setViolationCount] = useState(initial.violation_count);
  const [locked, setLocked] = useState(false);
  const [closedStatus, setClosedStatus] = useState<"submitted" | "expired" | null>(null);
  const [result, setResult] = useState<ExamResult | null>(null);
  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [remainingMs, setRemainingMs] = useState(() => new Date(initial.expires_at).getTime() - new Date(initial.server_now).getTime());

  const answersRef = useRef(answers);
  const clientSeqRef = useRef(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoSubmittedRef = useRef(false);
  const serverOffsetRef = useRef(0);
  const expiresAtMsRef = useRef(new Date(initial.expires_at).getTime());

  useEffect(() => {
    answersRef.current = answers;
  }, [answers]);

  // Set once on mount: how far the server's clock was from ours when this payload was issued, so
  // the countdown stays server-authoritative even if the client's clock is off.
  useEffect(() => {
    serverOffsetRef.current = new Date(initial.server_now).getTime() - Date.now();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const active = !locked && !closedStatus && !result;

  // ------------------------------------------------------------------------------- submit ----

  const handleSubmit = useCallback(async () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    clientSeqRef.current += 1;
    setSubmitting(true);
    try {
      const res = await submitAttempt.mutateAsync({ clientSeq: clientSeqRef.current, answers: toAnswerList(answersRef.current) });
      setResult(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 423) setLocked(true);
      else if (err instanceof ApiError && err.code === "ATTEMPT_EXPIRED") setClosedStatus("expired");
      else if (err instanceof ApiError && err.code === "ATTEMPT_NOT_ACTIVE") setClosedStatus("submitted");
      // otherwise the global toast already surfaced the error; let the student retry manually
    } finally {
      setSubmitting(false);
    }
  }, [submitAttempt]);

  // ------------------------------------------------------------------------- server-authoritative countdown ----

  useEffect(() => {
    const tick = () => {
      const remaining = expiresAtMsRef.current - (Date.now() + serverOffsetRef.current);
      setRemainingMs(remaining);
      if (remaining <= 0 && !autoSubmittedRef.current && active) {
        autoSubmittedRef.current = true;
        handleSubmit();
      }
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  // ------------------------------------------------------------------------------------ autosave ----

  const flushAutosave = useCallback(async () => {
    const seq = clientSeqRef.current;
    try {
      const res = await autosave.mutateAsync({ clientSeq: seq, answers: toAnswerList(answersRef.current) });
      expiresAtMsRef.current = new Date(res.expires_at).getTime();
    } catch (err) {
      if (err instanceof ApiError && err.status === 423) setLocked(true);
      else if (err instanceof ApiError && err.code === "ATTEMPT_EXPIRED") setClosedStatus("expired");
      else if (err instanceof ApiError && err.code === "ATTEMPT_NOT_ACTIVE") setClosedStatus("submitted");
    }
  }, [autosave]);

  function setAnswer(questionId: number, choiceId: number) {
    if (!active) return;
    setAnswers((prev) => ({ ...prev, [questionId]: prev[questionId] === choiceId ? null : choiceId }));
    clientSeqRef.current += 1;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(flushAutosave, 900);
  }

  // Safety-net autosave every 20s in case the debounced save above never fired.
  useEffect(() => {
    if (!active) return;
    const interval = setInterval(flushAutosave, 20_000);
    return () => clearInterval(interval);
  }, [active, flushAutosave]);

  // -------------------------------------------------------------------------- anti-cheat reporting ----

  const reportViolation = useCallback(async (type: ViolationType) => {
    try {
      const res = await reportViolationMutation.mutateAsync({ type, wasOffline: !navigator.onLine });
      setViolationCount(res.violation_count);
      if (res.locked) setLocked(true);
    } catch {
      // best-effort — the server debounces/ignores duplicates on its own
    }
  }, [reportViolationMutation]);

  useEffect(() => {
    if (!active) return;
    function onVisibility() {
      if (document.hidden) reportViolation("page_hidden");
    }
    function onBlur() {
      reportViolation("window_blur");
    }
    function onFullscreenChange() {
      if (!document.fullscreenElement) reportViolation("fullscreen_exit");
    }
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("fullscreenchange", onFullscreenChange);
    };
  }, [active, reportViolation]);

  // Refresh/navigation/tab-close guard while the attempt is still active — the backend deadline
  // (not this timer) is what actually decides when the attempt ends, so this is purely a "are you
  // sure" nudge, matching the documented tab-leave behavior above (no stronger claim than that).
  useEffect(() => {
    if (!active) return;
    function handler(e: BeforeUnloadEvent) {
      e.preventDefault();
      e.returnValue = "";
    }
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [active]);

  // ---------------------------------------------------------------------------------------- render ----

  if (locked) return <LockedScreen violationCount={violationCount} violationLimit={initial.violation_limit} />;
  if (closedStatus) return <ClosedScreen status={closedStatus} />;
  if (result) return <ResultScreen result={result} />;

  const question = questions[currentIndex] as AttemptQuestionOut;
  const passage = question.passage_id ? passageById.get(question.passage_id) : null;
  const answeredCount = questions.filter((q) => answers[q.id] !== null && answers[q.id] !== undefined).length;
  const minutes = Math.max(0, Math.floor(remainingMs / 60000));
  const seconds = Math.max(0, Math.floor((remainingMs % 60000) / 1000));
  const urgent = remainingMs <= 5 * 60_000;

  return (
    <div className="mx-auto max-w-5xl pb-24">
      <div className="sticky top-0 z-10 -mx-4 mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface/95 px-4 py-3 backdrop-blur">
        <div className="flex items-center gap-2 text-body-sm">
          <span>سؤال {currentIndex + 1} من {questions.length}</span>
          <span className="text-text-subtle">· تمت الإجابة على {answeredCount}</span>
        </div>
        <div className="flex items-center gap-2">
          {violationCount > 0 ? (
            <Badge tone="warning"><AlertTriangle size={12} /> {violationCount}/{initial.violation_limit} مخالفة</Badge>
          ) : null}
          {autosave.isPending ? <span className="text-caption text-text-subtle">جارٍ الحفظ...</span> : null}
          <Badge tone={urgent ? "danger" : "primary"}>
            <Clock size={13} /> {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
          </Badge>
          <Button
            variant="ghost" size="icon" className="size-8" aria-label="ملء الشاشة"
            onClick={() => document.documentElement.requestFullscreen?.().catch(() => {})}
          >
            <Expand size={15} />
          </Button>
        </div>
      </div>

      <div className="lg:grid lg:grid-cols-[360px_1fr] lg:gap-6">
        {passage ? <PassagePanel passage={passage} /> : null}

        <div className="rounded-lg border border-border bg-surface p-5">
          <div className="flex items-center gap-2 text-caption text-text-subtle">
            <span>{question.topic}</span> · <span>{question.points} نقطة</span>
          </div>
          {question.prompt_text ? <p className="mt-2 text-body-lg">{question.prompt_text}</p> : null}
          {question.image_url ? (
            <div className="relative mt-3 h-64 w-full overflow-hidden rounded-md bg-surface-2">
              <Image src={question.image_url} alt="" fill className="object-contain" unoptimized />
            </div>
          ) : null}

          <div className="mt-5 grid gap-2.5">
            {question.choices.map((choice) => {
              const selected = answers[question.id] === choice.id;
              return (
                <button
                  key={choice.id}
                  type="button"
                  onClick={() => setAnswer(question.id, choice.id)}
                  className={`flex items-center gap-3 rounded-md border p-3.5 text-start text-body-sm transition-colors ${selected ? "border-primary bg-primary-soft" : "border-border hover:bg-surface-2"}`}
                >
                  <span className={`flex size-8 shrink-0 items-center justify-center rounded-full border text-body-sm font-bold ${selected ? "border-primary bg-primary text-primary-fg" : "border-border-strong"}`}>
                    {choice.label}
                  </span>
                  {choice.text ? <span>{choice.text}</span> : null}
                </button>
              );
            })}
          </div>

          <div className="mt-6 flex items-center justify-between">
            <Button variant="secondary" disabled={currentIndex === 0} onClick={() => setCurrentIndex((i) => i - 1)}>السابق</Button>
            {currentIndex === questions.length - 1 ? (
              <Button onClick={() => setConfirmSubmitOpen(true)}>تسليم الامتحان</Button>
            ) : (
              <Button onClick={() => setCurrentIndex((i) => i + 1)}>التالي</Button>
            )}
          </div>
        </div>
      </div>

      <QuestionNavigator questions={questions} answers={answers} currentIndex={currentIndex} onSelect={setCurrentIndex} />

      <div className="mt-6 flex justify-center">
        <Button variant="secondary" onClick={() => setConfirmSubmitOpen(true)}>تسليم الامتحان</Button>
      </div>

      <ConfirmDialog
        open={confirmSubmitOpen}
        onOpenChange={setConfirmSubmitOpen}
        title="تسليم الامتحان"
        loading={submitting}
        onConfirm={async () => { setConfirmSubmitOpen(false); await handleSubmit(); }}
        description={
          answeredCount < questions.length
            ? `لسه فيه ${questions.length - answeredCount} سؤال بدون إجابة. هل تريد التسليم الآن؟ لا يمكن التراجع بعد التسليم.`
            : "لا يمكن التراجع بعد التسليم. هل أنت متأكد؟"
        }
      />
    </div>
  );
}

function QuestionNavigator({ questions, answers, currentIndex, onSelect }: {
  questions: AttemptQuestionOut[]; answers: Record<number, number | null>; currentIndex: number; onSelect: (i: number) => void;
}) {
  return (
    <div className="mt-6 flex flex-wrap gap-2">
      {questions.map((q, i) => {
        const answered = answers[q.id] !== null && answers[q.id] !== undefined;
        const current = i === currentIndex;
        return (
          <button
            key={q.id}
            type="button"
            onClick={() => onSelect(i)}
            aria-current={current}
            className={`flex size-9 items-center justify-center rounded-md text-body-sm font-medium transition-colors ${
              current ? "bg-primary text-primary-fg" : answered ? "bg-success-soft text-success-fg" : "bg-surface-2 text-text-muted"
            }`}
          >
            {answered && !current ? <CheckCircle2 size={15} /> : q.position}
          </button>
        );
      })}
    </div>
  );
}

function PassagePanel({ passage }: { passage: AttemptPassageOut }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="mb-4 rounded-lg border border-border bg-surface-2 lg:sticky lg:top-20 lg:mb-0 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between p-4 text-start lg:pointer-events-none">
        <span className="flex items-center gap-2 text-body-sm font-medium"><BookOpen size={16} /> {passage.title || "مقطع القراءة"}</span>
        <span className="lg:hidden">{open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</span>
      </button>
      <div className={`px-4 pb-4 lg:block ${open ? "block" : "hidden"}`}>
        {passage.image_url ? (
          <div className="relative mb-3 h-40 w-full overflow-hidden rounded-md bg-surface">
            <Image src={passage.image_url} alt="" fill className="object-contain" unoptimized />
          </div>
        ) : null}
        <p className="whitespace-pre-wrap text-body-sm leading-relaxed">{passage.body_text}</p>
      </div>
    </div>
  );
}
