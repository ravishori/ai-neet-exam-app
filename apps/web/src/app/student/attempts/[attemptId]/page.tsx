"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { assessmentApi } from "@/features/assessment/api";

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

export default function AttemptRunnerPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: attempt, isLoading } = useQuery({
    queryKey: ["assessment", "attempt", attemptId],
    queryFn: () => assessmentApi.getAttempt(attemptId),
  });

  const saveAnswer = useMutation({
    mutationFn: (vars: { content_item_id: string; selected_option: string | null }) =>
      assessmentApi.saveAnswer(attemptId, vars),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assessment", "attempt", attemptId] }),
  });
  const submit = useMutation({
    mutationFn: () => assessmentApi.submitAttempt(attemptId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assessment", "attempt", attemptId] }),
  });

  const remainingSec = useCountdown(attempt?.started_at ?? "", attempt?.assessment.duration_minutes ?? null, () => {
    if (attempt?.status === "IN_PROGRESS" && !submit.isPending) submit.mutate();
  });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }
  if (!attempt) return null;

  const isSubmitted = attempt.status === "SUBMITTED";

  return (
    <main className="flex flex-1 justify-center px-6 py-10">
      <div className="flex w-full max-w-2xl flex-col gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{attempt.assessment.title}</CardTitle>
              {isSubmitted ? (
                <Badge>Score: {attempt.score}</Badge>
              ) : (
                remainingSec !== null && <Badge variant="secondary">{Math.floor(remainingSec / 60)}:{String(remainingSec % 60).padStart(2, "0")}</Badge>
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

        {attempt.questions.map((q, idx) => (
          <Card key={q.content_item_id}>
            <CardHeader>
              <CardTitle className="text-base">
                {idx + 1}. {q.stem}
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {q.options.map((opt) => {
                const isSelected = q.selected_option === opt.label;
                const isCorrectOpt = isSubmitted && q.correct_option === opt.label;
                return (
                  <label
                    key={opt.label}
                    className={`flex cursor-pointer items-center gap-2 rounded-md border p-2 text-sm ${
                      isCorrectOpt
                        ? "border-green-600 bg-green-50 dark:bg-green-950"
                        : isSubmitted && isSelected && !isCorrectOpt
                          ? "border-destructive bg-destructive/10"
                          : isSelected
                            ? "border-primary"
                            : ""
                    }`}
                  >
                    <input
                      type="radio"
                      name={q.content_item_id}
                      disabled={isSubmitted}
                      checked={isSelected}
                      onChange={() => saveAnswer.mutate({ content_item_id: q.content_item_id, selected_option: opt.label })}
                    />
                    {opt.label}. {opt.text}
                  </label>
                );
              })}
              {isSubmitted && q.explanation && (
                <p className="mt-2 text-sm text-muted-foreground">{q.explanation}</p>
              )}
            </CardContent>
          </Card>
        ))}

        {!isSubmitted ? (
          <Button onClick={() => submit.mutate()} disabled={submit.isPending} className="w-fit">
            {submit.isPending ? "Submitting…" : "Submit"}
          </Button>
        ) : (
          <Button variant="outline" onClick={() => router.push("/student/attempts")} className="w-fit">
            Back to history
          </Button>
        )}
      </div>
    </main>
  );
}
