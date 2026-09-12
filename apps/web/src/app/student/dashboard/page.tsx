"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Loader2, Play, Target } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { MasteryBar } from "@/components/mastery-badge";
import { ScoreTrendChart } from "@/components/score-trend-chart";
import { Skeleton } from "@/components/ui/skeleton";
import {
  PageHeader,
  QuickLaunchHub,
  ReadinessGauge,
  computeReadinessIndex,
  SectionHeader,
  StatCard,
  StreakHeatmap,
  StudentPage,
  SubjectChip,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { useMe } from "@/features/auth/use-auth";
import { assessmentApi } from "@/features/assessment/api";
import { computeScoreTrend } from "@/features/assessment/analytics";
import { isNoQuestionsAvailable } from "@/features/assessment/thin-content";
import { practiceStartMessage, useStartPractice, PRACTICE_NOW_HERO_TEST_ID } from "@/features/assessment/use-start-practice";
import { learningApi, type RecommendationReason } from "@/features/learning/api";
import { cn } from "@/lib/utils";

const REASON_LABEL: Record<RecommendationReason, string> = {
  due_for_revision: "Due for revision",
  weak_concept: "Needs practice",
  new_concept: "Not started yet",
};

function PracticeNowButton({ conceptId, publishedCount }: { conceptId: string; publishedCount?: number }) {
  const start = useStartPractice();
  const unavailable = publishedCount === 0;

  return (
    <div className="flex flex-col items-stretch gap-1 sm:items-end">
      <Button
        type="button"
        size="default"
        variant="outline"
        className="min-h-11 min-w-[8.5rem] touch-manipulation"
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
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Starting…
          </>
        ) : (
          "Practice now"
        )}
      </Button>
      {unavailable && (
        <p id={`practice-unavailable-${conceptId}`} className="max-w-xs text-right text-xs text-muted-foreground">
          Practice is not available for this selection yet.
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

function HeroPracticeCta() {
  const start = useStartPractice();
  const emptyPool = start.isError && isNoQuestionsAvailable(start.error);

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
      <Button
        type="button"
        size="lg"
        className="min-h-12 touch-manipulation gap-2 px-5 text-base"
        disabled={start.isPending}
        aria-busy={start.isPending}
        aria-label="Practice now"
        title="Start an untimed practice session with published questions"
        data-testid={PRACTICE_NOW_HERO_TEST_ID}
        onClick={() => {
          if (start.isPending) return;
          start.mutate({ scope_type: "FULL", question_count: 30 });
        }}
      >
        {start.isPending ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Preparing your practice session…
          </>
        ) : (
          <>
            <Play className="size-4" aria-hidden />
            Practice now
          </>
        )}
      </Button>
      <Link
        href="/student/practice"
        className="inline-flex min-h-12 items-center justify-center rounded-lg border border-border bg-background px-5 text-base font-medium outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        Configure scope
      </Link>
      {emptyPool && (
        <Alert className="sm:basis-full" role="status">
          <AlertDescription className="space-y-2">
            <p className="font-medium">Practice is not available for this selection yet.</p>
            <p>{practiceStartMessage(start.error)}</p>
            <Link href="/student/practice" className="text-sm underline-offset-2 hover:underline">
              Configure a different scope
            </Link>
          </AlertDescription>
        </Alert>
      )}
      {start.isError && !emptyPool && (
        <Alert variant="destructive" className="sm:basis-full" role="alert">
          <AlertDescription className="space-y-2">
            <p>{practiceStartMessage(start.error)}</p>
            <button
              type="button"
              className="text-sm underline-offset-2 hover:underline"
              onClick={() => start.mutate({ scope_type: "FULL", question_count: 30 })}
            >
              Retry
            </button>
          </AlertDescription>
        </Alert>
      )}
      <p className="sr-only" aria-live="polite">
        {start.isPending ? "Preparing your practice session" : start.isError ? "Practice start failed" : ""}
      </p>
    </div>
  );
}

export default function StudentDashboardPage() {
  const { data: user, isLoading } = useMe();
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ["learning", "overview"],
    queryFn: learningApi.overview,
  });
  const { data: revisionDue } = useQuery({ queryKey: ["learning", "revision-due"], queryFn: learningApi.revisionDue });
  const { data: recommendations } = useQuery({
    queryKey: ["learning", "recommendations"],
    queryFn: learningApi.recommendations,
  });
  const { data: attempts } = useQuery({ queryKey: ["assessment", "attempts"], queryFn: assessmentApi.listAttempts });
  const scoreTrend = attempts ? computeScoreTrend(attempts) : [];
  const readiness = overview ? computeReadinessIndex(overview) : 0;

  const submitted = attempts?.filter((a) => a.status === "SUBMITTED") ?? [];
  const totalCorrect = submitted.reduce((n, a) => n + (a.correct_count ?? 0), 0);
  const totalIncorrect = submitted.reduce((n, a) => n + (a.incorrect_count ?? 0), 0);
  const accuracyDenom = totalCorrect + totalIncorrect;
  const accuracyPct = accuracyDenom > 0 ? Math.round((100 * totalCorrect) / accuracyDenom) : null;
  const attemptedQs = totalCorrect + totalIncorrect;
  const todayFocus =
    (revisionDue && revisionDue[0]?.concept_name) ||
    (recommendations && recommendations[0]?.concept_name) ||
    null;

  return (
    <StudentPage>
      <section className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
        <div className="space-y-4">
          <PageHeader
            eyebrow="Today’s focus"
            title={isLoading ? "Loading…" : `Welcome back, ${user?.first_name ?? user?.display_name ?? "aspirant"}`}
            description={
              todayFocus
                ? `Next up: ${todayFocus}. Practice now, or continue from your queues below.`
                : "Start an untimed practice session with published NEET questions — calm, focused, and ready when you are."
            }
          />
          <HeroPracticeCta />
          {user && !user.email_verified && (
            <p className="text-xs text-warning-foreground">
              <span className="rounded-md bg-warning/20 px-2 py-1 font-medium text-warning-foreground">
                Email not verified
              </span>
            </p>
          )}
        </div>
        <SurfaceCard glass lift={false} accent="none" className="justify-self-center p-6 lg:justify-self-end">
          {overviewLoading ? (
            <Skeleton className="size-[140px] rounded-full" />
          ) : (
            <ReadinessGauge value={readiness} label="NEET readiness" />
          )}
        </SurfaceCard>
      </section>

      <section className="space-y-3">
        <SectionHeader
          title="Continue preparation"
          description="Revision due and high-yield recommendations — practice the next concept."
        />
        <div className="grid gap-6 lg:grid-cols-2">
          <SurfaceCard accent="top" theme="physics">
            <SurfaceCardHeader>
              <SurfaceCardTitle>Continue learning</SurfaceCardTitle>
              <SurfaceCardDescription>Concepts due for another look.</SurfaceCardDescription>
            </SurfaceCardHeader>
            <SurfaceCardContent className="flex flex-col gap-3">
              {!revisionDue || revisionDue.length === 0 ? (
                <EmptyState
                  icon={BookOpen}
                  title="Nothing due right now"
                  description="Keep practicing available concepts, or browse subjects to build your queue."
                  action={
                    <Link href="/student/subjects" className={cn(buttonVariants({ variant: "outline", size: "touch" }))}>
                      Browse subjects
                    </Link>
                  }
                  className="py-8"
                />
              ) : (
                revisionDue.map((item) => (
                  <div
                    key={item.concept_id}
                    className="flex items-center justify-between gap-3 border-b border-border/60 pb-3 last:border-0 last:pb-0"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.concept_name}</p>
                      <p className="font-mono text-xs tabular-nums text-muted-foreground">
                        Score {item.mastery_score}
                        {item.published_question_count != null ? ` · ${item.published_question_count} Q` : ""}
                      </p>
                    </div>
                    <PracticeNowButton conceptId={item.concept_id} publishedCount={item.published_question_count} />
                  </div>
                ))
              )}
            </SurfaceCardContent>
          </SurfaceCard>

          <SurfaceCard accent="top" theme="chemistry">
            <SurfaceCardHeader>
              <SurfaceCardTitle>Recommended practice</SurfaceCardTitle>
              <SurfaceCardDescription>High-yield targets for today.</SurfaceCardDescription>
            </SurfaceCardHeader>
            <SurfaceCardContent className="flex flex-col gap-3">
              {!recommendations || recommendations.length === 0 ? (
                <EmptyState
                  icon={Target}
                  title="No recommendations yet"
                  description="Once you practice a few concepts, we’ll surface what to do next."
                  action={
                    <Link href="/student/practice" className={cn(buttonVariants({ variant: "outline", size: "touch" }))}>
                      Open practice arena
                    </Link>
                  }
                  className="py-8"
                />
              ) : (
                recommendations.map((item) => (
                  <div
                    key={item.concept_id}
                    className="flex items-center justify-between gap-3 border-b border-border/60 pb-3 last:border-0 last:pb-0"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.concept_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {REASON_LABEL[item.reason]}
                        {item.published_question_count != null ? ` · ${item.published_question_count} published` : ""}
                      </p>
                    </div>
                    <PracticeNowButton conceptId={item.concept_id} publishedCount={item.published_question_count} />
                  </div>
                ))
              )}
            </SurfaceCardContent>
          </SurfaceCard>
        </div>
      </section>

      <section className="space-y-3">
        <SectionHeader
          title="Your progress"
          description="Accuracy and volume from submitted attempts — why it matters for NEET readiness."
        />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <StatCard
            label="Accuracy"
            value={accuracyPct != null ? `${accuracyPct}%` : "—"}
            hint="Share of answers you got right"
          />
          <StatCard label="Questions" value={attemptedQs} hint="Answered across practice & mocks" />
          <StatCard label="Sessions" value={submitted.length} hint="Submitted attempts so far" />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <SurfaceCard accent="none">
          <SurfaceCardHeader>
            <SurfaceCardTitle>Mastery by subject</SurfaceCardTitle>
            <SurfaceCardDescription>
              Based on practice and mock attempts.{" "}
              <Link href="/student/analytics" className="underline-offset-2 hover:underline">
                Full progress
              </Link>
            </SurfaceCardDescription>
          </SurfaceCardHeader>
          <SurfaceCardContent className="flex flex-col gap-5">
            {!overview || overview.length === 0 ? (
              <EmptyState
                title="No mastery data yet"
                description="Browse subjects and start practicing to build your map."
                action={
                  <Link href="/student/subjects" className={cn(buttonVariants({ variant: "outline", size: "touch" }))}>
                    Browse subjects
                  </Link>
                }
                className="py-8"
              />
            ) : (
              overview.map((s) => (
                <div key={s.subject_id} className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <div className="flex items-center gap-2">
                      <SubjectChip subject={s.subject_name} />
                      <span className="font-medium">{s.subject_name}</span>
                    </div>
                    <span className="font-mono text-xs tabular-nums text-muted-foreground">
                      {s.concepts_attempted}/{s.concepts_total} · {s.average_score}%
                    </span>
                  </div>
                  <MasteryBar score={s.average_score} />
                </div>
              ))
            )}
          </SurfaceCardContent>
        </SurfaceCard>

        <div className="flex flex-col gap-6">
          <SurfaceCard accent="none">
            <SurfaceCardContent>
              <StreakHeatmap attempts={attempts} />
            </SurfaceCardContent>
          </SurfaceCard>

          {attempts && attempts.some((a) => a.status === "SUBMITTED") && (
            <SurfaceCard accent="none">
              <SurfaceCardHeader>
                <SurfaceCardTitle>Accuracy trend</SurfaceCardTitle>
                <SurfaceCardDescription>
                  <Link href="/student/attempts" className="hover:underline">
                    Last {scoreTrend.length} submitted attempts
                  </Link>
                </SurfaceCardDescription>
              </SurfaceCardHeader>
              <SurfaceCardContent>
                <ScoreTrendChart points={scoreTrend} />
              </SurfaceCardContent>
            </SurfaceCard>
          )}
        </div>
      </div>

      <section className="space-y-3">
        <SectionHeader title="More ways to prepare" description="Subjects, mocks, flashcards, and the question bank." />
        <QuickLaunchHub />
      </section>
    </StudentPage>
  );
}
