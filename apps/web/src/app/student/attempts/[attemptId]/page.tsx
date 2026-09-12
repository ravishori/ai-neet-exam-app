"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { QuestionPalette, type PaletteQuestionStatus } from "@/components/question-palette";
import { QuestionPanel } from "@/components/question-panel";
import { TopicPerformanceBreakdown } from "@/components/topic-performance-breakdown";
import { assessmentApi, type Confidence, type SaveAnswerInput } from "@/features/assessment/api";
import { cn } from "@/lib/utils";

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
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">
          Q {current} / {total}
        </span>
        <span className="font-mono tabular-nums">{pct}% answered</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={label}
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full rounded-full bg-primary transition-[width] duration-300 ease-out motion-reduce:transition-none" style={{ width: `${pct}%` }} />
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

  function commitAnswer(patch: Partial<AnswerState>) {
    if (!question) return;
    const next: AnswerState = { ...(localAnswer ?? { selected_option: null, confidence: null, marked_for_review: false }), ...patch };
    setLocalAnswer(next);
    saveAnswer.mutate({ content_item_id: question.content_item_id, ...next });
  }

  function goTo(index: number) {
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
      <main className="flex-1 px-4 py-10 sm:px-6 sm:py-12">
        <div className="mx-auto flex max-w-4xl flex-col gap-3" aria-busy="true" aria-live="polite">
          <p className="text-sm text-muted-foreground">Loading your practice session…</p>
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-64 w-full" />
        </div>
      </main>
    );
  }

  if (isError) {
    return (
      <main className="mx-auto flex w-full max-w-lg flex-1 flex-col gap-4 px-4 py-12">
        <Alert variant="destructive" role="alert">
          <AlertTitle>Unable to load practice</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>{error instanceof Error ? error.message : "Something went wrong loading this attempt."}</p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" onClick={() => refetch()}>
                Retry
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => router.push("/student/dashboard")}>
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
    <main className={`flex flex-1 justify-center px-4 py-4 sm:px-6 sm:py-8 ${isTimedExam ? "exam-mode" : ""}`}>
      <div className="grid w-full max-w-5xl grid-cols-1 gap-4 pb-28 lg:grid-cols-[240px_1fr] lg:pb-4">
        <div className="flex flex-col gap-4 lg:order-2">
          <Card className={isTimedExam ? "border-foreground/20 shadow-sm" : "surface-glass border-0"}>
            <CardHeader className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                    {isTimedExam ? "Exam simulator" : attempt.assessment.assessment_type === "MOCK" ? "Mock review" : "NEET practice"}
                  </p>
                  <CardTitle className="text-xl sm:text-2xl">{attempt.assessment.title}</CardTitle>
                </div>
                {isSubmitted ? (
                  <Badge className="font-mono tabular-nums">Score: {attempt.score}</Badge>
                ) : (
                  remainingSec !== null && (
                    <Badge variant="secondary" className="font-mono text-base tabular-nums tracking-tight">
                      {Math.floor(remainingSec / 60)}:{String(remainingSec % 60).padStart(2, "0")}
                    </Badge>
                  )
                )}
              </div>
              <ProgressBar current={currentIndex + 1} total={questions.length} answered={answeredCount} />
              <CardDescription>
                {attempt.assessment.question_count} questions · +{attempt.assessment.marks_per_question} / −
                {attempt.assessment.negative_marks_per_question}
              </CardDescription>
            </CardHeader>
            {isSubmitted && (
              <CardContent className="flex flex-col gap-4">
                <div className="flex flex-wrap gap-4 text-sm">
                  <span className="text-success">{attempt.correct_count} correct</span>
                  <span className="text-destructive">{attempt.incorrect_count} incorrect</span>
                  <span className="text-muted-foreground">{attempt.skipped_count} skipped</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="default"
                    className="min-h-11"
                    onClick={() => {
                      const firstMistake = questions.findIndex((q) => q.is_correct === false);
                      goTo(firstMistake >= 0 ? firstMistake : 0);
                    }}
                  >
                    Review mistakes
                  </Button>
                  <Link
                    href="/student/practice"
                    className={cn(buttonVariants({ variant: "outline" }), "min-h-11")}
                  >
                    Practice weak topics
                  </Link>
                  <Link
                    href="/student/dashboard"
                    className={cn(buttonVariants({ variant: "ghost" }), "min-h-11")}
                  >
                    Back to dashboard
                  </Link>
                </div>
              </CardContent>
            )}
          </Card>

          {isSubmitted && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Performance by topic</CardTitle>
                <CardDescription>How you did on each topic covered in this attempt.</CardDescription>
              </CardHeader>
              <CardContent>
                <TopicPerformanceBreakdown questions={questions} />
              </CardContent>
            </Card>
          )}

          <div className="overflow-x-auto lg:hidden">
            <QuestionPalette
              statuses={statuses}
              currentIndex={currentIndex}
              onJump={goTo}
              className="grid-flow-col grid-cols-none grid-rows-1 auto-cols-max"
            />
          </div>

          <Card className={isTimedExam ? "shadow-sm" : "surface-glass border-0"}>
            <CardContent className="pt-6">
              <QuestionPanel
                question={displayedQuestion}
                index={currentIndex}
                total={questions.length}
                isSubmitted={isSubmitted}
                onSelectOption={(label) => commitAnswer({ selected_option: label })}
                onSetConfidence={(confidence) => commitAnswer({ confidence })}
                onToggleMarkForReview={() => commitAnswer({ marked_for_review: !displayedQuestion.marked_for_review })}
              />
            </CardContent>
          </Card>

          {/* Desktop / tablet inline controls */}
          <div className="hidden flex-wrap items-center justify-between gap-2 sm:flex">
            <Button type="button" variant="outline" className="min-h-11" onClick={() => goTo(currentIndex - 1)} disabled={currentIndex === 0}>
              <ChevronLeft className="size-4" aria-hidden="true" /> Previous
            </Button>

            {!isSubmitted ? (
              <div className="flex flex-wrap items-center gap-2">
                {currentIndex < questions.length - 1 && (
                  <Button type="button" variant="outline" className="min-h-11" onClick={() => goTo(currentIndex + 1)}>
                    Save &amp; Next <ChevronRight className="size-4" aria-hidden="true" />
                  </Button>
                )}
                <Button
                  type="button"
                  className="min-h-11"
                  onClick={() => setSubmitConfirmOpen(true)}
                  disabled={submit.isPending}
                >
                  {submit.isPending ? "Submitting…" : "Submit"}
                </Button>
              </div>
            ) : currentIndex < questions.length - 1 ? (
              <Button type="button" variant="outline" className="min-h-11" onClick={() => goTo(currentIndex + 1)}>
                Next <ChevronRight className="size-4" aria-hidden="true" />
              </Button>
            ) : (
              <Button type="button" variant="outline" className="min-h-11" onClick={() => router.push("/student/attempts")}>
                Back to history
              </Button>
            )}
          </div>
        </div>

        <div className="hidden lg:order-1 lg:block">
          <Card className={`sticky top-4 ${isTimedExam ? "shadow-sm" : "surface-glass border-0"}`}>
            <CardHeader>
              <CardTitle className="text-sm">Question grid</CardTitle>
              <CardDescription className="text-xs">Answered · Visited · Unvisited · Review</CardDescription>
            </CardHeader>
            <CardContent>
              <QuestionPalette statuses={statuses} currentIndex={currentIndex} onJump={goTo} />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Mobile sticky practice controls */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-glass-border bg-glass/95 px-3 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] backdrop-blur-xl sm:hidden">
        <div className="mx-auto flex max-w-lg items-center justify-between gap-2">
          <Button type="button" variant="outline" className="min-h-11 flex-1" onClick={() => goTo(currentIndex - 1)} disabled={currentIndex === 0}>
            Prev
          </Button>
          {!isSubmitted ? (
            <>
              {currentIndex < questions.length - 1 ? (
                <Button type="button" variant="outline" className="min-h-11 flex-1" onClick={() => goTo(currentIndex + 1)}>
                  Next
                </Button>
              ) : null}
              <Button
                type="button"
                className="min-h-11 flex-1"
                onClick={() => setSubmitConfirmOpen(true)}
                disabled={submit.isPending}
              >
                {submit.isPending ? "…" : "Submit"}
              </Button>
            </>
          ) : (
            <Button
              type="button"
              variant="outline"
              className="min-h-11 flex-1"
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
            <Button type="button" variant="outline" onClick={() => setSubmitConfirmOpen(false)}>
              Keep practicing
            </Button>
            <Button
              type="button"
              onClick={() => {
                setSubmitConfirmOpen(false);
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
