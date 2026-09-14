"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock, Loader2, Play, Target } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ScopePicker, type Scope } from "@/components/scope-picker";
import { Skeleton } from "@/components/ui/skeleton";
import {
  PageHeader,
  SectionHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { assessmentApi } from "@/features/assessment/api";
import { isNoQuestionsAvailable } from "@/features/assessment/thin-content";
import {
  PRACTICE_ARENA_START_TEST_ID,
  practiceStartMessage,
  useStartPractice,
} from "@/features/assessment/use-start-practice";
import { learningApi, type RecommendationReason } from "@/features/learning/api";
import { cn } from "@/lib/utils";

const REASON_LABEL: Record<RecommendationReason, string> = {
  due_for_revision: "Due for revision",
  weak_concept: "Needs practice",
  new_concept: "Not started yet",
};

/** Quiet concept starter — same CONCEPT generate path; does not compete with the primary CTA. */
function ConceptPracticeLink({
  conceptId,
  publishedCount,
}: {
  conceptId: string;
  publishedCount?: number;
}) {
  const start = useStartPractice();
  const unavailable = publishedCount === 0;

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      <button
        type="button"
        className={cn(
          "inline-flex min-h-11 items-center gap-1 touch-manipulation px-1.5 text-sm font-medium",
          "text-muted-foreground outline-none transition-colors",
          "hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50",
          "disabled:pointer-events-none disabled:opacity-50",
        )}
        disabled={start.isPending || unavailable}
        aria-busy={start.isPending}
        aria-disabled={unavailable}
        aria-describedby={unavailable ? `practice-unavailable-${conceptId}` : undefined}
        title={
          unavailable
            ? "Practice is not available — no published questions for this concept yet"
            : "Start a practice session for this concept"
        }
        onClick={() => {
          if (start.isPending || unavailable) return;
          start.mutate({ scope_type: "CONCEPT", scope_id: conceptId });
        }}
      >
        {start.isPending ? (
          <>
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
            Starting…
          </>
        ) : (
          <>
            Practice
            <ArrowRight className="size-3.5 opacity-70" aria-hidden />
          </>
        )}
      </button>
      {unavailable && (
        <p
          id={`practice-unavailable-${conceptId}`}
          className="max-w-[9rem] text-right text-[0.7rem] leading-snug text-muted-foreground"
        >
          Not available yet
        </p>
      )}
      {start.isError && (
        <Alert variant="destructive" className="max-w-xs py-2" role="alert">
          <AlertDescription className="space-y-2 text-xs">
            <p>{practiceStartMessage(start.error)}</p>
            <button
              type="button"
              className="underline-offset-2 hover:underline"
              onClick={() => start.mutate({ scope_type: "CONCEPT", scope_id: conceptId })}
            >
              Retry
            </button>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

export default function PracticePage() {
  const [scope, setScope] = useState<Scope | null>(null);
  const start = useStartPractice();

  const { data: recommendations, isLoading: recommendationsLoading } = useQuery({
    queryKey: ["learning", "recommendations"],
    queryFn: learningApi.recommendations,
  });
  const { data: attempts, isLoading: attemptsLoading } = useQuery({
    queryKey: ["assessment", "attempts"],
    queryFn: assessmentApi.listAttempts,
  });

  const inProgress = attempts?.find((a) => a.status === "IN_PROGRESS") ?? null;

  const onGenerate = () => {
    start.mutate(
      scope
        ? { scope_type: scope.scope_type, scope_id: scope.scope_id, question_count: 30 }
        : { scope_type: "FULL", question_count: 30 },
    );
  };

  const emptyPool = start.isError && isNoQuestionsAvailable(start.error);
  const scopeSummary = scope
    ? `${scope.scope_type.charAt(0)}${scope.scope_type.slice(1).toLowerCase()} — ${scope.label}`
    : "Any published question (full pool)";

  return (
    <StudentPage width="lg" className="gap-7 lg:gap-9">
      {/* Hero — one dominant start action */}
      <section className="page-atmosphere relative overflow-hidden rounded-3xl border border-border/50 px-4 py-5 sm:px-8 sm:py-8">
        <div className="relative grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-end lg:gap-10">
          <div className="min-w-0 space-y-3.5 sm:space-y-5">
            <PageHeader
              className="gap-1.5 sm:items-start sm:gap-2"
              eyebrow="Practice command center"
              title="Start published practice"
              description="Untimed drills with no negative marking. Scope to a subject, chapter, topic, or concept — or leave open for any published question."
            />

            {inProgress ? (
              <p className="text-sm text-muted-foreground" role="status">
                You have an unfinished session.{" "}
                <Link
                  href={`/student/attempts/${inProgress.id}`}
                  className="font-medium text-foreground underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  Resume session
                </Link>
                <span className="text-border" aria-hidden>
                  {" "}
                  ·{" "}
                </span>
                or start a new one below.
              </p>
            ) : attemptsLoading ? (
              <Skeleton className="h-5 w-48" />
            ) : null}

            <div className="flex flex-col gap-2.5 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
              <Button
                type="button"
                size="lg"
                onClick={onGenerate}
                disabled={start.isPending}
                aria-busy={start.isPending}
                aria-label="Start practice"
                title="Start an untimed practice session with published questions"
                data-testid={PRACTICE_ARENA_START_TEST_ID}
                className="min-h-12 touch-manipulation gap-2 px-6 text-base font-semibold shadow-sm"
              >
                {start.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                    Preparing your practice session…
                  </>
                ) : (
                  <>
                    <Play className="size-4" aria-hidden />
                    Start practice
                  </>
                )}
              </Button>
              <p className="text-sm text-muted-foreground sm:max-w-xs">
                Current scope: <span className="font-medium text-foreground">{scopeSummary}</span>
              </p>
            </div>

            <p className="sr-only" aria-live="polite">
              {start.isPending
                ? "Preparing your practice session"
                : emptyPool
                  ? "No published questions for this selection"
                  : ""}
            </p>
          </div>

          {/* Mode clarity — informational, not competing CTAs */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <div className="rounded-2xl border border-subject-physics-border bg-subject-physics-muted/50 px-4 py-3.5">
              <div className="mb-1.5 flex items-center gap-2">
                <span className="flex size-8 items-center justify-center rounded-lg bg-background/70 text-subject-physics">
                  <Target className="size-3.5" aria-hidden />
                </span>
                <p className="text-sm font-semibold text-subject-physics">Untimed practice</p>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Up to 30 published questions. No timer, no −1. Ideal for focused NEET drills.
              </p>
            </div>
            <div className="rounded-2xl border border-border/60 bg-background/50 px-4 py-3.5">
              <div className="mb-1.5 flex items-center gap-2">
                <span className="flex size-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <Clock className="size-3.5" aria-hidden />
                </span>
                <p className="text-sm font-semibold text-foreground">Timed mock</p>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">
                Exam marking (+4 / −1) lives on the mock arena — not here.{" "}
                <Link
                  href="/student/mock-tests"
                  className="font-medium text-foreground underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                >
                  Open mock tests
                </Link>
              </p>
            </div>
          </div>
        </div>
      </section>

      {emptyPool && (
        <Alert role="status">
          <AlertDescription className="space-y-2">
            <p className="font-medium">Practice is not available for this selection yet.</p>
            <p>{practiceStartMessage(start.error)}</p>
            <p className="text-sm text-muted-foreground">
              No published questions are currently available for this scope. Try another topic, chapter, or start
              with any published question.
            </p>
            <div className="flex flex-wrap gap-3 text-sm">
              <button type="button" className="underline-offset-2 hover:underline" onClick={onGenerate}>
                Retry
              </button>
              <button
                type="button"
                className="underline-offset-2 hover:underline"
                onClick={() => start.mutate({ scope_type: "FULL", question_count: 30 })}
              >
                Practice any published question
              </button>
              <Link href="/student/subjects" className="underline-offset-2 hover:underline">
                Browse subjects
              </Link>
              <Link href="/student/dashboard" className="underline-offset-2 hover:underline">
                Return to dashboard
              </Link>
            </div>
          </AlertDescription>
        </Alert>
      )}
      {start.isError && !emptyPool && (
        <Alert variant="destructive" role="alert">
          <AlertDescription className="space-y-2">
            <p>{practiceStartMessage(start.error)}</p>
            <button type="button" className="text-sm underline-offset-2 hover:underline" onClick={onGenerate}>
              Retry
            </button>
          </AlertDescription>
        </Alert>
      )}

      {/* Scope configuration */}
      <section className="space-y-4">
        <SectionHeader
          title="Configure scope"
          description="Narrow the pool before you start. Leave blank for any published question."
        />
        <SurfaceCard theme="physics" accent="top" lift={false} glass={false} level="l1">
          <SurfaceCardHeader>
            <div className="flex items-center gap-2">
              <span className="flex size-9 items-center justify-center rounded-xl bg-subject-physics-muted text-subject-physics">
                <Target className="size-4" aria-hidden />
              </span>
              <div>
                <SurfaceCardTitle>Session scope</SurfaceCardTitle>
                <SurfaceCardDescription>
                  Published questions only — drafts never appear here.
                </SurfaceCardDescription>
              </div>
            </div>
          </SurfaceCardHeader>
          <SurfaceCardContent className="flex flex-col gap-4">
            <ScopePicker onChange={setScope} />
            <p className="text-sm text-muted-foreground">
              Active:{" "}
              <span className="font-medium text-foreground">
                {scope ? `${scope.scope_type.toLowerCase()} — ${scope.label}` : "any published question"}
              </span>
            </p>
            {/* Secondary start — ghost only, so hero stays dominant */}
            <Button
              type="button"
              variant="ghost"
              onClick={onGenerate}
              disabled={start.isPending}
              aria-busy={start.isPending}
              className={cn(
                "min-h-12 w-full touch-manipulation justify-center gap-2 sm:w-fit",
                "text-muted-foreground hover:text-foreground",
                "dark:bg-transparent dark:hover:bg-muted/40",
              )}
            >
              {start.isPending ? "Preparing…" : "Start with this scope"}
              <ArrowRight className="size-3.5 opacity-70" aria-hidden />
            </Button>
          </SurfaceCardContent>
        </SurfaceCard>
      </section>

      {/* Recommendations from existing learning API */}
      <section className="space-y-4">
        <SectionHeader
          title="Suggested concepts"
          description="High-yield targets from your learning profile — practice one at a time."
        />
        <SurfaceCard accent="none" lift={false} glass={false} level="l1">
          <SurfaceCardContent className="flex flex-col gap-3 py-4">
            {recommendationsLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full rounded-xl" />
                <Skeleton className="h-12 w-full rounded-xl" />
                <Skeleton className="h-12 w-full rounded-xl" />
              </div>
            ) : !recommendations || recommendations.length === 0 ? (
              <EmptyState
                title="No suggestions yet"
                description="Once you practice a few concepts, we’ll surface what to drill next."
                action={
                  <Link
                    href="/student/subjects"
                    className={cn(buttonVariants({ variant: "outline", size: "touch" }))}
                  >
                    Browse subjects
                  </Link>
                }
                className="border-0 py-6"
              />
            ) : (
              recommendations.map((item) => (
                <div
                  key={item.concept_id}
                  className="flex items-center justify-between gap-3 border-b border-border/50 pb-3 last:border-0 last:pb-0"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.concept_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {REASON_LABEL[item.reason]}
                      {item.published_question_count != null
                        ? ` · ${item.published_question_count} published`
                        : ""}
                    </p>
                  </div>
                  <ConceptPracticeLink
                    conceptId={item.concept_id}
                    publishedCount={item.published_question_count}
                  />
                </div>
              ))
            )}
          </SurfaceCardContent>
        </SurfaceCard>
      </section>
    </StudentPage>
  );
}
