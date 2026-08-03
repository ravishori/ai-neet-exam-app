"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { QuestionPalette, type PaletteQuestionStatus } from "@/components/question-palette";
import { QuestionPanel } from "@/components/question-panel";
import { TopicPerformanceBreakdown } from "@/components/topic-performance-breakdown";
import { assessmentApi, type Confidence, type SaveAnswerInput } from "@/features/assessment/api";

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

export default function AttemptRunnerPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [currentIndex, setCurrentIndex] = useState(0);

  const { data: attempt, isLoading } = useQuery({
    queryKey: ["assessment", "attempt", attemptId],
    queryFn: () => assessmentApi.getAttempt(attemptId),
  });

  const questions = attempt?.questions ?? [];
  const question = questions[currentIndex];
  const isSubmitted = attempt?.status === "SUBMITTED";

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

  // Local answer mirror for the current question — lets option-select/confidence/
  // mark-for-review feel instant, and gives the time-tracking effect below a
  // stable snapshot to read from when the question changes.
  const [localAnswer, setLocalAnswer] = useState<AnswerState | null>(null);
  const localAnswerRef = useRef<AnswerState | null>(null);
  localAnswerRef.current = localAnswer;
  const attemptStatusRef = useRef(attempt?.status);
  attemptStatusRef.current = attempt?.status;

  useEffect(() => {
    setLocalAnswer(
      question
        ? { selected_option: question.selected_option, confidence: question.confidence, marked_for_review: question.marked_for_review }
        : null
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentIndex, question?.content_item_id]);

  // Commit accumulated time-on-question whenever the student navigates away
  // from a question — a question can be revisited many times before submit,
  // so the backend accumulates rather than overwrites (see assessment_service.py).
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
    setCurrentIndex(Math.max(0, Math.min(questions.length - 1, index)));
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
      <main className="flex-1 px-6 py-12">
        <div className="mx-auto flex max-w-4xl flex-col gap-3" aria-busy="true" aria-live="polite">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-64 w-full" />
        </div>
      </main>
    );
  }
  if (!attempt || !question) return null;

  const displayedQuestion = { ...question, ...(localAnswer ?? {}) };
  const statuses: PaletteQuestionStatus[] = questions.map((q, idx) => ({
    answered: (idx === currentIndex ? localAnswer?.selected_option : q.selected_option) != null,
    markedForReview: (idx === currentIndex ? localAnswer?.marked_for_review : q.marked_for_review) ?? false,
  }));

  return (
    <main className="flex flex-1 justify-center px-4 py-6 sm:px-6 sm:py-10">
      <div className="grid w-full max-w-5xl grid-cols-1 gap-4 lg:grid-cols-[220px_1fr]">
        <div className="flex flex-col gap-4 lg:order-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>{attempt.assessment.title}</CardTitle>
                {isSubmitted ? (
                  <Badge>Score: {attempt.score}</Badge>
                ) : (
                  remainingSec !== null && (
                    <Badge variant="secondary">
                      {Math.floor(remainingSec / 60)}:{String(remainingSec % 60).padStart(2, "0")}
                    </Badge>
                  )
                )}
              </div>
              <CardDescription>
                {attempt.assessment.question_count} questions · +{attempt.assessment.marks_per_question} / −
                {attempt.assessment.negative_marks_per_question}
              </CardDescription>
            </CardHeader>
            {isSubmitted && (
              <CardContent className="flex gap-4 text-sm">
                <span className="text-green-600 dark:text-green-400">{attempt.correct_count} correct</span>
                <span className="text-destructive">{attempt.incorrect_count} incorrect</span>
                <span className="text-muted-foreground">{attempt.skipped_count} skipped</span>
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

          {/* Mobile/tablet: horizontal palette strip above the question. */}
          <div className="overflow-x-auto lg:hidden">
            <QuestionPalette statuses={statuses} currentIndex={currentIndex} onJump={goTo} className="grid-flow-col grid-cols-none grid-rows-1 auto-cols-max" />
          </div>

          <Card>
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

          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button type="button" variant="outline" onClick={() => goTo(currentIndex - 1)} disabled={currentIndex === 0}>
              <ChevronLeft className="size-4" aria-hidden="true" /> Previous
            </Button>

            {!isSubmitted ? (
              <div className="flex flex-wrap items-center gap-2">
                {currentIndex < questions.length - 1 && (
                  <Button type="button" variant="outline" onClick={() => goTo(currentIndex + 1)}>
                    Save &amp; Next <ChevronRight className="size-4" aria-hidden="true" />
                  </Button>
                )}
                <Button type="button" onClick={() => submit.mutate()} disabled={submit.isPending}>
                  {submit.isPending ? "Submitting…" : "Submit"}
                </Button>
              </div>
            ) : currentIndex < questions.length - 1 ? (
              <Button type="button" variant="outline" onClick={() => goTo(currentIndex + 1)}>
                Next <ChevronRight className="size-4" aria-hidden="true" />
              </Button>
            ) : (
              <Button type="button" variant="outline" onClick={() => router.push("/student/attempts")}>
                Back to history
              </Button>
            )}
          </div>
        </div>

        {/* Desktop: sidebar palette. */}
        <div className="hidden lg:order-1 lg:block">
          <Card className="sticky top-4">
            <CardHeader>
              <CardTitle className="text-sm">Questions</CardTitle>
            </CardHeader>
            <CardContent>
              <QuestionPalette statuses={statuses} currentIndex={currentIndex} onJump={goTo} />
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
