"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Download, ExternalLink, FileQuestion, FileText, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyLessonDetail, useUpdateLessonProgress } from "@/hooks/use-my-courses";
import { ApiError } from "@/lib/api";

// Not found / unauthorized both render this same card, on purpose: the backend returns the same
// 404 for "this lesson doesn't exist", "you don't have access to it", and "it belongs to a
// different course than the one you have access to" -- never confirming which, so a student can't
// probe for the existence of a lesson they can't see (same discipline as the exam runner).
function LessonNotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 rounded-lg border border-border bg-surface-2 py-14 px-6 text-center">
      <FileQuestion size={28} className="text-text-muted" />
      <h2 className="text-h3">الدرس غير موجود أو غير متاح لك</h2>
      <p className="text-body-sm text-text-muted">تأكد إنك مشترك في الكورس، أو إن الرابط صحيح.</p>
      <Button asChild className="mt-2"><Link href="/courses">كورساتي</Link></Button>
    </div>
  );
}

export default function LessonPlayerPage() {
  const params = useParams<{ id: string; lessonId: string }>();
  const courseId = Number(params.id);
  const lessonId = Number(params.lessonId);
  const router = useRouter();

  const { data: lesson, isLoading, error, refetch } = useMyLessonDetail(lessonId);
  const updateProgress = useUpdateLessonProgress(lessonId, courseId);

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  // The backend only ever checks access via the lesson's own real course (never trusts the URL's
  // course id), so a mismatched course id in the URL would otherwise silently render the lesson
  // under the wrong course's breadcrumb/back-link. Treated the same as not-found here, not a
  // generic error, since nothing is actually broken -- the URL just doesn't describe a real place.
  if (error instanceof ApiError && error.status !== 404) {
    return <ErrorState message={error.message} onRetry={() => refetch()} />;
  }
  if (error || !lesson || lesson.course_id !== courseId) return <LessonNotFound />;

  async function markComplete() {
    try {
      const result = await updateProgress.mutateAsync(true);
      if (result.points_awarded > 0) toast.success(`تم إكمال الدرس! +${result.points_awarded} نقطة`);
      else toast.success("تم إكمال الدرس");
    } catch {
      // toast already shown globally
    }
  }

  const recording = lesson.recording;

  return (
    <div>
      <div className="flex items-center gap-1.5 text-body-sm text-text-muted">
        <Link href={`/courses/${courseId}`} className="hover:text-text">{lesson.course_title}</Link>
        <span>/</span>
        <span>{lesson.title}</span>
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_280px]">
        <div>
          <div className="overflow-hidden rounded-lg border border-border bg-[var(--brand-900)]">
            <div className="flex items-center justify-between px-4 py-2 text-caption text-[var(--brand-200)]">
              <span className="flex items-center gap-1.5"><ShieldCheck size={14} /> وصول محمي للدرس</span>
              <span>Talent Academy</span>
            </div>
            {recording?.embed_url ? (
              <div className="aspect-video">
                <iframe src={recording.embed_url} title={lesson.title} allowFullScreen className="h-full w-full" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" />
              </div>
            ) : recording?.url ? (
              <div className="flex aspect-video flex-col items-center justify-center gap-3 text-white">
                <p className="text-body-sm text-[var(--brand-200)]">التسجيل متاح على رابط خارجي</p>
                <Button asChild>
                  <a href={recording.url} target="_blank" rel="noreferrer">
                    فتح التسجيل <ExternalLink size={16} />
                  </a>
                </Button>
              </div>
            ) : (
              <div className="flex aspect-video items-center justify-center text-body-sm text-[var(--brand-200)]">لا يوجد تسجيل لهذا الدرس بعد</div>
            )}
          </div>

          <div className="mt-5 flex items-center justify-between gap-3">
            <div>
              <h1 className="text-h1">{lesson.title}</h1>
              {lesson.description ? <p className="mt-1 text-body-sm text-text-muted">{lesson.description}</p> : null}
            </div>
            <Button variant={lesson.completed ? "secondary" : "primary"} onClick={markComplete} loading={updateProgress.isPending} disabled={lesson.completed}>
              {lesson.completed ? <><Check size={17} /> تم إكمال الدرس</> : <><CheckCircle2 size={17} /> علّم كمكتمل</>}
            </Button>
          </div>

          <section className="mt-6">
            <h3 className="text-h3">المرفقات</h3>
            {lesson.materials.length > 0 ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {lesson.materials.map((m) => (
                  <a key={m.id} href={m.url ?? undefined} target="_blank" rel="noreferrer" className="flex items-center gap-3 rounded-md border border-border px-3.5 py-3 text-body-sm hover:bg-surface-2">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-primary-soft text-primary-soft-fg"><FileText size={17} /></span>
                    <span className="flex-1">{m.title}</span>
                    {m.is_downloadable ? <Download size={15} className="text-text-subtle" /> : null}
                  </a>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-body-sm text-text-subtle">لا يوجد مرفقات لهذا الدرس بعد.</p>
            )}
          </section>

          <div className="mt-8 flex items-center justify-between border-t border-border pt-5">
            {lesson.prev_id ? (
              <Button variant="secondary" onClick={() => router.push(`/courses/${courseId}/lessons/${lesson.prev_id}`)}>
                <ArrowRight size={16} className="rtl-flip" /> الدرس السابق
              </Button>
            ) : <span />}
            {lesson.next_id ? (
              <Button onClick={() => router.push(`/courses/${courseId}/lessons/${lesson.next_id}`)}>
                الدرس التالي <ArrowLeft size={16} className="rtl-flip" />
              </Button>
            ) : (
              <Button asChild><Link href={`/courses/${courseId}`}>العودة للكورس</Link></Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
