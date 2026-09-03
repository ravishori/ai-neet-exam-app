"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Play } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MasteryBar } from "@/components/mastery-badge";
import { ScoreTrendChart } from "@/components/score-trend-chart";
import {
  QuickLaunchHub,
  ReadinessGauge,
  computeReadinessIndex,
  StreakHeatmap,
  SubjectChip,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/features/auth/use-auth";
import { assessmentApi } from "@/features/assessment/api";
import { computeScoreTrend } from "@/features/assessment/analytics";
import { isNoQuestionsAvailable } from "@/features/assessment/thin-content";
import { practiceStartMessage, useStartPractice } from "@/features/assessment/use-start-practice";
import { learningApi, type RecommendationReason } from "@/features/learning/api";

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
        onClick={() => start.mutate({ scope_type: "CONCEPT", scope_id: conceptId })}
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
          Practice is not available for this selection yet. No published questions are currently available.
        </p>
      )}
      {start.isError && (
        <Alert variant="destructive" className="max-w-xs py-2" role="alert">
          <AlertDescription className="space-y-2 text-xs">
            <p>{practiceStartMessage(start.error)}</p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="underline-offset-2 hover:underline"
                onClick={() => start.mutate({ scope_type: "CONCEPT", scope_id: conceptId })}
              >
                Retry
              </button>
              {isNoQuestionsAvailable(start.error) && (
                <Link href="/student/practice" className="underline-offset-2 hover:underline">
                  Open practice arena
                </Link>
              )}
            </div>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}

function HeroPracticeCta() {
  const start = useStartPractice();
  const seedStart = useStartPractice();
  const seedV2Start = useStartPractice();
  const emptyPool = start.isError && isNoQuestionsAvailable(start.error);
  const seedEmpty = seedStart.isError && isNoQuestionsAvailable(seedStart.error);
  const seedV2Empty = seedV2Start.isError && isNoQuestionsAvailable(seedV2Start.error);

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
      <Button
        type="button"
        size="lg"
        className="min-h-12 touch-manipulation gap-2 px-5 text-base"
        disabled={start.isPending}
        aria-busy={start.isPending}
        aria-label="Practice now with any published question"
        onClick={() => start.mutate({ scope_type: "FULL", question_count: 30 })}
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
      <Button
        type="button"
        size="lg"
        variant="outline"
        className="min-h-12 touch-manipulation gap-2 px-5 text-base"
        disabled={seedStart.isPending}
        aria-busy={seedStart.isPending}
        aria-label="Practice Seed V1 — exact 30 published questions"
        onClick={() => seedStart.mutate({ scope_type: "SEED_V1", question_count: 30 })}
      >
        {seedStart.isPending ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Preparing Seed V1…
          </>
        ) : (
          "Practice Seed V1"
        )}
      </Button>
      <Button
        type="button"
        size="lg"
        variant="outline"
        className="min-h-12 touch-manipulation gap-2 px-5 text-base"
        disabled={seedV2Start.isPending}
        aria-busy={seedV2Start.isPending}
        aria-label="Practice Seed V2 — exact 100 published questions"
        onClick={() => seedV2Start.mutate({ scope_type: "SEED_V2", question_count: 100 })}
      >
        {seedV2Start.isPending ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Preparing Seed V2…
          </>
        ) : (
          "Practice Seed V2"
        )}
      </Button>
      <Link
        href="/student/practice"
        className="inline-flex min-h-12 items-center justify-center rounded-lg border border-border bg-background px-5 text-base font-medium outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50"
      >
        Open practice arena
      </Link>
      {emptyPool && (
        <Alert className="sm:basis-full" role="status">
          <AlertDescription className="space-y-2">
            <p className="font-medium">Practice is not available for this selection yet.</p>
            <p>{practiceStartMessage(start.error)}</p>
            <p className="text-sm text-muted-foreground">No published questions are currently available.</p>
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
      {seedStart.isError && (
        <Alert variant="destructive" className="sm:basis-full" role="alert">
          <AlertDescription className="space-y-2">
            <p>{practiceStartMessage(seedStart.error)}</p>
            {!seedEmpty && (
              <button
                type="button"
                className="text-sm underline-offset-2 hover:underline"
                onClick={() => seedStart.mutate({ scope_type: "SEED_V1", question_count: 30 })}
              >
                Retry Seed V1
              </button>
            )}
          </AlertDescription>
        </Alert>
      )}
      {seedV2Start.isError && (
        <Alert variant="destructive" className="sm:basis-full" role="alert">
          <AlertDescription className="space-y-2">
            <p>{practiceStartMessage(seedV2Start.error)}</p>
            {!seedV2Empty && (
              <button
                type="button"
                className="text-sm underline-offset-2 hover:underline"
                onClick={() => seedV2Start.mutate({ scope_type: "SEED_V2", question_count: 100 })}
              >
                Retry Seed V2
              </button>
            )}
          </AlertDescription>
        </Alert>
      )}
      <p className="sr-only" aria-live="polite">
        {start.isPending || seedStart.isPending || seedV2Start.isPending
          ? "Preparing your practice session"
          : start.isError || seedStart.isError || seedV2Start.isError
            ? "Practice start failed"
            : ""}
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

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-6 pb-24 sm:px-6 sm:py-8 lg:pb-8 animate-fade-slide-up">
      <section className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
        <div className="space-y-4">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Command dashboard</p>
          <h1 className="font-heading text-3xl font-bold tracking-tight sm:text-4xl">
            {isLoading ? "Loading…" : `Welcome back, ${user?.first_name ?? user?.display_name ?? "aspirant"}`}
          </h1>
          <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
            Start an untimed practice session with published NEET questions, revise due concepts, or browse the bank —
            without leaving the command center.
          </p>
          <HeroPracticeCta />
          {user && (
            <div className="flex flex-wrap gap-2 pt-1">
              {user.roles.map((role) => (
                <Badge key={role} variant="secondary">
                  {role}
                </Badge>
              ))}
              {!user.email_verified && <Badge variant="outline">Email not verified</Badge>}
            </div>
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
        <h2 className="font-heading text-lg font-semibold">Quick launch</h2>
        <QuickLaunchHub />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <SurfaceCard accent="top" theme="physics">
          <SurfaceCardHeader>
            <SurfaceCardTitle>Revision queue</SurfaceCardTitle>
            <SurfaceCardDescription>Concepts due for another look.</SurfaceCardDescription>
          </SurfaceCardHeader>
          <SurfaceCardContent className="flex flex-col gap-3">
            {!revisionDue || revisionDue.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nothing due with published practice content — keep practicing available concepts, or{" "}
                <Link href="/student/subjects" className="underline-offset-2 hover:underline">
                  browse subjects
                </Link>
                .
              </p>
            ) : (
              revisionDue.map((item) => (
                <div key={item.concept_id} className="flex items-center justify-between gap-3 border-b border-border/60 pb-3 last:border-0 last:pb-0">
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
              <p className="text-sm text-muted-foreground">
                No practice recommendations with published questions yet.{" "}
                <Link href="/student/practice" className="underline-offset-2 hover:underline">
                  Open practice arena
                </Link>{" "}
                or{" "}
                <Link href="/student/subjects" className="underline-offset-2 hover:underline">
                  pick a subject
                </Link>
                .
              </p>
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

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <SurfaceCard accent="none">
          <SurfaceCardHeader>
            <SurfaceCardTitle>Mastery by subject</SurfaceCardTitle>
            <SurfaceCardDescription>Based on practice and mock attempts.</SurfaceCardDescription>
          </SurfaceCardHeader>
          <SurfaceCardContent className="flex flex-col gap-5">
            {!overview || overview.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                <Link href="/student/subjects" className="underline-offset-2 hover:underline">
                  Browse subjects
                </Link>{" "}
                to begin building mastery.
              </p>
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
    </main>
  );
}
