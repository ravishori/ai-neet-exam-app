"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { QuestionPalette, type PaletteQuestionStatus } from "@/components/question-palette";
import { QuestionPanel } from "@/components/question-panel";
import { TopicPerformanceBreakdown } from "@/components/topic-performance-breakdown";
import { assessmentApi, type Confidence, type SaveAnswerInput } from "@/features/assessment/api";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

function studentSafeMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.message) return error.message;
  return fallback;
}

function useCountdown(startedAt: string, durationMinutes: number | null, onExpire: () => void) {
  const [remainingSec, setRemainingSec] = useState<number | null>(null);
  const firedRef = useRef(false);

  useEffect(() => {
    if (!durationMinutes) return;
    const deadline = new Date(startedAt).getTime() + durationMinutes * 60_000;

    const tick = () => {
      const remaining = Math.max(0, Math.round((deadline - Date.now()) / 1000));
      setRemainingSec(remaining);
      if (remaining <= 0 && !firedRef.current) {
        firedRef.current = true;
        onExpire();
      }
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startedAt, durationMinutes]);

  return remainingSec;
}

type AnswerState = { selected_option: string | null; confidence: Confidence | null; marked_for_review: boolean };

function ProgressBar({ current, total, answered }: { current: number; total: number; answered: number }) {
  const pct = total > 0 ? Math.round((answered / total) * 100) : 0;
  const label = `Progress: question ${current} of ${total}, ${answered} answered`;
  return (
    <div className="space-y-2" data-testid="practice-runner-progress">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-[0.65rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Session</p>
          <p className="font-mono text-lg font-semibold tabular-nums tracking-tight text-foreground">
            {current}
            <span className="mx-1 text-muted-foreground/70" aria-hidden>
              /
            </span>
            {total}
          </p>
        </div>
        <p className="pb-0.5 text-right text-xs text-muted-foreground">
          <span className="font-mono tabular-nums text-foreground">{answered}</span> answered
          <span className="mx-1.5 text-border" aria-hidden>
            ·
          </span>
          <span className="font-mono tabular-nums">{pct}%</span>
        </p>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={label}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out motion-reduce:transition-none"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function AttemptRunnerPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [visited, setVisited] = useState<Set<number>>(() => new Set([0]));
  const [submitConfirmOpen, setSubmitConfirmOpen] = useState(false);

  const {
    data: attempt,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["assessment", "attempt", attemptId],
    queryFn: () => assessmentApi.getAttempt(attemptId),
  });

  const questions = attempt?.questions ?? [];
  const question = questions[currentIndex];
  const isSubmitted = attempt?.status === "SUBMITTED";
  const isTimedExam = (attempt?.assessment.duration_minutes ?? null) != null && !isSubmitted;

  const saveAnswer = useMutation({
    mutationFn: (vars: SaveAnswerInput) => assessmentApi.saveAnswer(attemptId, vars),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assessment", "attempt", attemptId] }),
  });
  const submit = useMutation({
    mutationFn: () => assessmentApi.submitAttempt(attemptId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assessment", "attempt", attemptId] }),
  });

  const remainingSec = useCountdown(attempt?.started_at ?? "", attempt?.assessment.duration_minutes ?? null, () => {
    if (attempt?.status === "IN_PROGRESS" && !submit.isPending) submit.mutate();
  });

  const [localAnswer, setLocalAnswer] = useState<AnswerState | null>(null);
  const localAnswerRef = useRef<AnswerState | null>(null);
  localAnswerRef.current = localAnswer;
  const attemptStatusRef = useRef(attempt?.status);
  attemptStatusRef.current = attempt?.status;

  useEffect(() => {
    setLocalAnswer(
      question
        ? { selected_option: question.selected_option, confidence: question.confidence, marked_for_review: question.marked_for_review }
        : null,
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentIndex, question?.content_item_id]);

  useEffect(() => {
    const itemId = question?.content_item_id;
    const entryTime = Date.now();
    return () => {
      const state = localAnswerRef.current;
      if (!itemId || !state || attemptStatusRef.current !== "IN_PROGRESS") return;
      const elapsed = Math.round((Date.now() - entryTime) / 1000);
      if (elapsed <= 0) return;
      saveAnswer.mutate({ content_item_id: itemId, ...state, time_spent_seconds: elapsed });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentIndex]);

  // Autosave coalescing (P0-runner): rapid toggling of option / confidence /
  // mark-for-review must not fire one POST per keystroke. Buffer patches in a
  // ref and flush a single mutation after a short quiet window (or on
  // navigation / unmount via the effect above).
  const pendingSaveRef = useRef<{
    itemId: string;
    state: AnswerState;
    entry: number;
  } | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function flushSave() {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    const pending = pendingSaveRef.current;
    if (!pending) return;
    pendingSaveRef.current = null;
    const elapsed = Math.max(1, Math.round((Date.now() - pending.entry) / 1000));
    saveAnswer.mutate({ content_item_id: pending.itemId, ...pending.state, time_spent_seconds: elapsed });
  }

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  function commitAnswer(patch: Partial<AnswerState>) {
    if (!question) return;
    const next: AnswerState = { ...(localAnswer ?? { selected_option: null, confidence: null, marked_for_review: false }), ...patch };
    setLocalAnswer(next);
    if (attemptStatusRef.current !== "IN_PROGRESS") return;
    const prev = pendingSaveRef.current;
    pendingSaveRef.current = {
      itemId: question.content_item_id,
      state: next,
      entry: prev && prev.itemId === question.content_item_id ? prev.entry : Date.now(),
    };
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(flushSave, 400);
  }

  function goTo(index: number) {
    // Flush any debounced answer save before navigating so the next-question
    // fetch does not race with an in-flight autosave.
    flushSave();
    const next = Math.max(0, Math.min(questions.length - 1, index));
    setVisited((prev) => {
      if (prev.has(next)) return prev;
      const copy = new Set(prev);
      copy.add(next);
      return copy;
    });
    setCurrentIndex(next);
  }

  useEffect(() => {
    function handleKeydown(e: KeyboardEvent) {
      if (isSubmitted || !question) return;
      const tag = (document.activeElement as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      const key = e.key.toUpperCase();
      const optIdx = ["A", "B", "C", "D"].indexOf(key);
      if (optIdx >= 0 && question.options[optIdx]) {
        commitAnswer({ selected_option: question.options[optIdx].label });
      } else if (e.key === "ArrowRight") {
        goTo(currentIndex + 1);
      } else if (e.key === "ArrowLeft") {
        goTo(currentIndex - 1);
      }
    }
    window.addEventListener("keydown", handleKeydown);
    return () => window.removeEventListener("keydown", handleKeydown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, isSubmitted, currentIndex, localAnswer]);

  if (isLoading) {
    return (
      <main className="flex-1 px-4 py-8 sm:px-6 sm:py-10">
        <div className="mx-auto flex max-w-4xl flex-col gap-4" aria-busy="true" aria-live="polite">
          <p className="text-sm text-muted-foreground">Loading your practice session…</p>
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-72 w-full rounded-2xl" />
        </div>
      </main>
    );
  }

  if (isError) {
    return (
      <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-4 px-4 py-12 pb-24 sm:px-6">
        <Alert variant="destructive" role="alert">
          <AlertTitle>Unable to load practice</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>
              {studentSafeMessage(
                error,
                "We couldn’t load this practice session right now. Try again, or return to the dashboard.",
              )}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="touch" onClick={() => refetch()}>
                Retry
              </Button>
              <Button type="button" size="touch" variant="outline" onClick={() => router.push("/student/dashboard")}>
                Dashboard
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  if (!attempt) {
    return (
      <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-4 px-4 py-12">
        <Alert role="status">
          <AlertTitle>Attempt not found</AlertTitle>
          <AlertDescription>
            <Link href="/student/practice" className="underline-offset-2 hover:underline">
              Start a new practice session
            </Link>
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  if (questions.length === 0) {
    return (
      <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-4 px-4 py-12">
        <Alert role="status">
          <AlertTitle>No questions are currently available</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>This session has no questions. Return to the practice arena and try a different scope.</p>
            <Link href="/student/practice" className="underline-offset-2 hover:underline">
              Open practice arena
            </Link>
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  if (!question) return null;

  const displayedQuestion = { ...question, ...(localAnswer ?? {}) };
  const answeredCount = questions.filter((q, idx) =>
    idx === currentIndex ? localAnswer?.selected_option != null : q.selected_option != null,
  ).length;
  const statuses: PaletteQuestionStatus[] = questions.map((q, idx) => ({
    answered: (idx === currentIndex ? localAnswer?.selected_option : q.selected_option) != null,
    markedForReview: (idx === currentIndex ? localAnswer?.marked_for_review : q.marked_for_review) ?? false,
    visited: visited.has(idx) || idx === currentIndex,
  }));

  return (
    <main
      className={`flex flex-1 justify-center px-3 py-3 sm:px-6 sm:py-6 ${isTimedExam ? "exam-mode" : ""}`}
      data-testid="practice-runner"
    >
      <div className="grid w-full max-w-5xl grid-cols-1 gap-3 pb-28 sm:gap-4 lg:grid-cols-[220px_1fr] lg:pb-4">
        <div className="flex flex-col gap-3 sm:gap-4 lg:order-2">
          <SurfaceCard
            accent="none"
            glass={!isTimedExam}
            lift={false}
            className={isTimedExam ? "border border-foreground/20 shadow-sm" : undefined}
          >
            <SurfaceCardHeader className="space-y-3.5 pb-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-meta">
                    {isTimedExam
                      ? "Exam simulator"
                      : attempt.assessment.assessment_type === "MOCK"
                        ? "Mock review"
                        : "NEET practice"}
                  </p>
                  <SurfaceCardTitle className="truncate text-lg sm:text-xl">
                    {attempt.assessment.title}
                  </SurfaceCardTitle>
                  <SurfaceCardDescription className="mt-1">
                    {attempt.assessment.question_count} questions · +{attempt.assessment.marks_per_question} / −
                    {attempt.assessment.negative_marks_per_question}
                  </SurfaceCardDescription>
                </div>
                {isSubmitted ? (
                  <Badge className="font-mono tabular-nums text-base" data-testid="practice-runner-score">
                    Score: {attempt.score}
                  </Badge>
                ) : remainingSec !== null ? (
                  <div
                    className="rounded-xl border border-border/70 bg-background/80 px-3 py-2 text-right shadow-xs"
                    data-testid="practice-runner-timer"
                    role="timer"
                    aria-live="polite"
                    aria-label={`Time remaining ${Math.floor(remainingSec / 60)} minutes ${remainingSec % 60} seconds`}
                  >
                    <p className="text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                      Remaining
                    </p>
                    <p className="font-mono text-xl font-semibold tabular-nums tracking-tight text-foreground">
                      {Math.floor(remainingSec / 60)}:{String(remainingSec % 60).padStart(2, "0")}
                    </p>
                  </div>
                ) : null}
              </div>
              <ProgressBar current={currentIndex + 1} total={questions.length} answered={answeredCount} />
            </SurfaceCardHeader>
            {isSubmitted && (
              <SurfaceCardContent className="flex flex-col gap-5">
                <div>
                  <h2 className="text-h2">How did you perform?</h2>
                  <p className="text-small text-muted-foreground">
                    Review the score, then pick a clear next step.
                  </p>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center sm:max-w-md">
                  <div className="rounded-xl border border-success/30 bg-success/10 px-3 py-3">
                    <p className="font-mono text-lg font-semibold tabular-nums text-success">{attempt.correct_count}</p>
                    <p className="text-caption">Correct</p>
                  </div>
                  <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-3">
                    <p className="font-mono text-lg font-semibold tabular-nums text-destructive">
                      {attempt.incorrect_count}
                    </p>
                    <p className="text-caption">Incorrect</p>
                  </div>
                  <div className="rounded-xl border border-border bg-muted/40 px-3 py-3">
                    <p className="font-mono text-lg font-semibold tabular-nums text-muted-foreground">
                      {attempt.skipped_count}
                    </p>
                    <p className="text-caption">Skipped</p>
                  </div>
                </div>
                <div>
                  <h3 className="text-h3 mb-2">What should you do next?</h3>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="default"
                      size="touch"
                      onClick={() => {
                        const firstMistake = questions.findIndex((q) => q.is_correct === false);
                        goTo(firstMistake >= 0 ? firstMistake : 0);
                      }}
                    >
                      Review mistakes
                    </Button>
                    <Link
                      href="/student/practice"
                      className={cn(buttonVariants({ variant: "outline", size: "touch" }))}
                    >
                      Practice weak topics
                    </Link>
                    <Link
                      href="/student/dashboard"
                      className={cn(buttonVariants({ variant: "ghost", size: "touch" }))}
                    >
                      Back to dashboard
                    </Link>
                  </div>
                </div>
              </SurfaceCardContent>
            )}
          </SurfaceCard>

          {isSubmitted && (
            <SurfaceCard accent="none" lift={false}>
              <SurfaceCardHeader>
                <SurfaceCardTitle className="text-base">Performance by topic</SurfaceCardTitle>
                <SurfaceCardDescription>Where you were strong — and where to drill next.</SurfaceCardDescription>
              </SurfaceCardHeader>
              <SurfaceCardContent>
                <TopicPerformanceBreakdown questions={questions} />
              </SurfaceCardContent>
            </SurfaceCard>
          )}

          <div className="overflow-x-auto lg:hidden">
            <QuestionPalette
              statuses={statuses}
              currentIndex={currentIndex}
              onJump={goTo}
              className="grid-flow-col grid-cols-none grid-rows-1 auto-cols-max"
            />
          </div>

          <SurfaceCard accent="none" glass={!isTimedExam} lift={false} className="border-border/60">
            <SurfaceCardContent className="pt-5 sm:pt-6">
              <QuestionPanel
                question={displayedQuestion}
                index={currentIndex}
                total={questions.length}
                isSubmitted={isSubmitted}
                onSelectOption={(label) => commitAnswer({ selected_option: label })}
                onSetConfidence={(confidence) => commitAnswer({ confidence })}
                onToggleMarkForReview={() => commitAnswer({ marked_for_review: !displayedQuestion.marked_for_review })}
              />
            </SurfaceCardContent>
          </SurfaceCard>

          {/* Desktop / tablet inline controls — Next is primary forward action */}
          <div className="hidden flex-wrap items-center justify-between gap-2 sm:flex">
            <Button
              type="button"
              variant="outline"
              size="touch"
              className="min-h-12"
              onClick={() => goTo(currentIndex - 1)}
              disabled={currentIndex === 0}
            >
              <ChevronLeft className="size-4" aria-hidden="true" /> Previous
            </Button>

            {!isSubmitted && (
              <p
                aria-live="polite"
                className="text-xs text-muted-foreground"
                data-testid="practice-runner-save-status"
              >
                {saveAnswer.isPending ? "Saving…" : saveAnswer.isSuccess ? "Saved" : ""}
              </p>
            )}

            {!isSubmitted ? (
              <div className="flex flex-wrap items-center gap-2">
                {currentIndex < questions.length - 1 ? (
                  <>
                    <Button
                      type="button"
                      variant="ghost"
                      size="touch"
                      className="min-h-12 text-muted-foreground"
                      onClick={() => setSubmitConfirmOpen(true)}
                      disabled={submit.isPending}
                    >
                      {submit.isPending ? "Submitting…" : "Submit"}
                    </Button>
                    <Button
                      type="button"
                      size="touch"
                      className="min-h-12 px-5 font-semibold"
                      data-testid="practice-runner-next"
                      onClick={() => goTo(currentIndex + 1)}
                    >
                      Save &amp; Next <ChevronRight className="size-4" aria-hidden="true" />
                    </Button>
                  </>
                ) : (
                  <Button
                    type="button"
                    size="touch"
                    className="min-h-12 px-5 font-semibold"
                    data-testid="practice-runner-submit"
                    onClick={() => setSubmitConfirmOpen(true)}
                    disabled={submit.isPending}
                  >
                    {submit.isPending ? "Submitting…" : "Submit attempt"}
                  </Button>
                )}
              </div>
            ) : currentIndex < questions.length - 1 ? (
              <Button
                type="button"
                size="touch"
                className="min-h-12"
                data-testid="practice-runner-next"
                onClick={() => goTo(currentIndex + 1)}
              >
                Next <ChevronRight className="size-4" aria-hidden="true" />
              </Button>
            ) : (
              <Button type="button" variant="outline" size="touch" className="min-h-12" onClick={() => router.push("/student/attempts")}>
                Back to history
              </Button>
            )}
          </div>
        </div>

        <div className="hidden lg:order-1 lg:block">
          <SurfaceCard
            accent="none"
            glass={!isTimedExam}
            lift={false}
            className={`sticky top-4 ${isTimedExam ? "border border-border shadow-sm" : ""}`}
          >
            <SurfaceCardHeader className="pb-3">
              <SurfaceCardTitle className="text-sm">Question map</SurfaceCardTitle>
              <SurfaceCardDescription className="text-xs">Jump by number · answered · review</SurfaceCardDescription>
            </SurfaceCardHeader>
            <SurfaceCardContent>
              <QuestionPalette statuses={statuses} currentIndex={currentIndex} onJump={goTo} />
            </SurfaceCardContent>
          </SurfaceCard>
        </div>
      </div>

      {/* Mobile sticky practice controls — Next/Submit primary */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-glass-border bg-glass/95 px-3 py-2.5 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur-xl sm:hidden">
        <div className="mx-auto flex max-w-lg items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="touch"
            className="min-h-12 flex-1"
            onClick={() => goTo(currentIndex - 1)}
            disabled={currentIndex === 0}
          >
            Prev
          </Button>
          {!isSubmitted ? (
            currentIndex < questions.length - 1 ? (
              <>
                <Button
                  type="button"
                  variant="ghost"
                  size="touch"
                  className="min-h-12 flex-1 text-muted-foreground"
                  onClick={() => setSubmitConfirmOpen(true)}
                  disabled={submit.isPending}
                >
                  {submit.isPending ? "…" : "Submit"}
                </Button>
                <Button
                  type="button"
                  size="touch"
                  className="min-h-12 flex-[1.35] font-semibold"
                  data-testid="practice-runner-next-mobile"
                  onClick={() => goTo(currentIndex + 1)}
                >
                  Next
                </Button>
              </>
            ) : (
              <Button
                type="button"
                size="touch"
                className="min-h-12 flex-[2] font-semibold"
                data-testid="practice-runner-submit-mobile"
                onClick={() => setSubmitConfirmOpen(true)}
                disabled={submit.isPending}
              >
                {submit.isPending ? "…" : "Submit"}
              </Button>
            )
          ) : (
            <Button
              type="button"
              size="touch"
              className="min-h-12 flex-[2]"
              onClick={() => (currentIndex < questions.length - 1 ? goTo(currentIndex + 1) : router.push("/student/attempts"))}
            >
              {currentIndex < questions.length - 1 ? "Next" : "Done"}
            </Button>
          )}
        </div>
      </div>

      <Dialog open={submitConfirmOpen} onOpenChange={setSubmitConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Submit this attempt?</DialogTitle>
            <DialogDescription>
              You&apos;ve answered {answeredCount} of {questions.length} questions. Unanswered items will count as
              skipped. You can&apos;t change answers after submit.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" size="touch" onClick={() => setSubmitConfirmOpen(false)}>
              Keep practicing
            </Button>
            <Button
              type="button"
              size="touch"
              onClick={() => {
                setSubmitConfirmOpen(false);
                flushSave();
                submit.mutate();
              }}
              disabled={submit.isPending}
            >
              {submit.isPending ? "Submitting…" : "Confirm submit"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
