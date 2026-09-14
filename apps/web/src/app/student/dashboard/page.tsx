"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpen, Loader2, Play, Target } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ScoreTrendChart } from "@/components/score-trend-chart";
import { Skeleton } from "@/components/ui/skeleton";
import {
  PageHeader,
  QuickLaunchHub,
  ReadinessGauge,
  computeReadinessIndex,
  SectionHeader,
  StreakHeatmap,
  StudentPage,
  SubjectChip,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
  resolveSubjectTheme,
  SUBJECT_THEME_CLASSES,
} from "@/components/ds";
import { useMe } from "@/features/auth/use-auth";
import { assessmentApi } from "@/features/assessment/api";
import { computeScoreTrend } from "@/features/assessment/analytics";
import { isNoQuestionsAvailable } from "@/features/assessment/thin-content";
import {
  practiceStartMessage,
  useStartPractice,
  PRACTICE_NOW_HERO_TEST_ID,
} from "@/features/assessment/use-start-practice";
import { learningApi, type RecommendationReason } from "@/features/learning/api";
import { cn } from "@/lib/utils";

const REASON_LABEL: Record<RecommendationReason, string> = {
  due_for_revision: "Due for revision",
  weak_concept: "Needs practice",
  new_concept: "Not started yet",
};

/** Inline fetch-error alert used by the four dashboard section queries.
 * Without this, a failed fetch collapses into the "empty" branch and the
 * student sees "Nothing here yet" copy that does not describe reality. */
function FetchErrorAlert({
  message,
  onRetry,
  testId,
  isRetrying,
}: {
  message: string;
  onRetry: () => void;
  testId: string;
  isRetrying: boolean;
}) {
  return (
    <Alert variant="destructive" role="alert" data-testid={testId} className="py-3">
      <AlertDescription className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <span>{message}</span>
        <button
          type="button"
          className="font-medium underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:opacity-60"
          onClick={onRetry}
          disabled={isRetrying}
          aria-busy={isRetrying}
        >
          {isRetrying ? "Retrying…" : "Retry"}
        </button>
      </AlertDescription>
    </Alert>
  );
}

/** Quiet concept action — preserves CONCEPT practice start without competing with the hero CTA. */
function ConceptPracticeLink({
  conceptId,
  publishedCount,
  label = "Practice",
}: {
  conceptId: string;
  publishedCount?: number;
  label?: string;
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
            : `Start a practice session for ${label.toLowerCase() === "review" ? "revision" : "this concept"}`
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
            {label}
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

function HeroPracticeCta() {
  const start = useStartPractice();
  const emptyPool = start.isError && isNoQuestionsAvailable(start.error);

  return (
    <div className="flex flex-col gap-2.5 sm:flex-row sm:flex-wrap sm:items-center sm:gap-3">
      <Button
        type="button"
        size="lg"
        className="min-h-12 touch-manipulation gap-2 px-6 text-base font-semibold shadow-sm"
        disabled={start.isPending}
        aria-busy={start.isPending}
        aria-label="Continue practice"
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
            Continue practice
          </>
        )}
      </Button>
      <Link
        href="/student/practice"
        className={cn(
          buttonVariants({ variant: "ghost", size: "lg" }),
          // Soft secondary: muted text; avoid loud filled/outline competition in dark mode
          "min-h-12 touch-manipulation px-4 text-base font-medium text-muted-foreground",
          "hover:bg-muted/60 hover:text-foreground",
          "dark:bg-transparent dark:text-muted-foreground dark:hover:bg-muted/40 dark:hover:text-foreground",
        )}
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
        {start.isPending
          ? "Preparing your practice session"
          : start.isError
            ? "Practice start failed"
            : ""}
      </p>
    </div>
  );
}

function MetricPill({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 rounded-xl border border-border/50 bg-background/60 px-3 py-2 backdrop-blur-sm sm:px-3.5 sm:py-2.5">
      <span className="text-[0.65rem] font-medium uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </span>
      <span className="font-mono text-base font-semibold tabular-nums tracking-tight text-foreground sm:text-lg">
        {value}
      </span>
    </div>
  );
}

function SubjectMasteryRow({
  subjectId,
  subjectName,
  conceptsAttempted,
  conceptsTotal,
  averageScore,
}: {
  subjectId: string;
  subjectName: string;
  conceptsAttempted: number;
  conceptsTotal: number;
  averageScore: number;
}) {
  const theme = resolveSubjectTheme(subjectName);
  const tones = SUBJECT_THEME_CLASSES[theme];
  const coverage =
    conceptsTotal > 0 ? Math.round((conceptsAttempted / conceptsTotal) * 100) : 0;
  const notStarted = conceptsAttempted === 0 && averageScore === 0;
  const masteryPct = Math.max(0, Math.min(100, averageScore));

  return (
    <div
      className={cn(
        "flex flex-col gap-2.5 rounded-2xl border px-3 py-3 sm:px-3.5 sm:py-3.5",
        tones.border,
        tones.muted,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span
            className={cn("size-3 shrink-0 rounded-md", tones.accentBar)}
            aria-hidden
          />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <SubjectChip subject={subjectName} />
              <span className={cn("truncate text-sm font-semibold", tones.text)}>
                {subjectName}
              </span>
            </div>
            <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
              {notStarted
                ? "Not started yet"
                : `Coverage ${coverage}% of concepts attempted`}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <p className="font-mono text-xs tabular-nums text-muted-foreground">
            <span className="sr-only">Average mastery </span>
            {notStarted ? "—" : `${averageScore}%`}
            <span className="mx-1 text-border" aria-hidden>
              ·
            </span>
            <span className="sr-only">Coverage </span>
            {conceptsAttempted}/{conceptsTotal}
          </p>
          {notStarted ? (
            <Link
              href={`/student/subjects/${subjectId}`}
              className={cn(
                "inline-flex min-h-11 items-center gap-1 touch-manipulation text-sm font-medium",
                tones.text,
                "outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50",
              )}
            >
              Open
              <ArrowRight className="size-3.5 opacity-70" aria-hidden />
            </Link>
          ) : null}
        </div>
      </div>
      <div
        className={cn("h-2.5 w-full overflow-hidden rounded-full", tones.muted)}
        role="progressbar"
        aria-label={
          notStarted
            ? `${subjectName} not started yet`
            : `${subjectName} mastery ${averageScore} percent`
        }
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(masteryPct)}
      >
        {/* At 0%, a soft subject-tinted track + inset mark keeps identity without faking progress */}
        {notStarted ? (
          <div
            className={cn("h-full w-2 rounded-full opacity-80", tones.accentBar)}
            aria-hidden
          />
        ) : (
          <div
            className={cn("h-full rounded-full transition-all", tones.accentBar)}
            style={{ width: `${masteryPct}%` }}
          />
        )}
      </div>
    </div>
  );
}

export default function StudentDashboardPage() {
  const { data: user, isLoading } = useMe();
  const overviewQuery = useQuery({
    queryKey: ["learning", "overview"],
    queryFn: learningApi.overview,
  });
  const { data: overview, isLoading: overviewLoading } = overviewQuery;
  const revisionQuery = useQuery({
    queryKey: ["learning", "revision-due"],
    queryFn: learningApi.revisionDue,
  });
  const { data: revisionDue, isLoading: revisionLoading } = revisionQuery;
  const recommendationsQuery = useQuery({
    queryKey: ["learning", "recommendations"],
    queryFn: learningApi.recommendations,
  });
  const { data: recommendations, isLoading: recommendationsLoading } = recommendationsQuery;
  const attemptsQuery = useQuery({
    queryKey: ["assessment", "attempts"],
    queryFn: assessmentApi.listAttempts,
  });
  const { data: attempts, isLoading: attemptsLoading } = attemptsQuery;
  const scoreTrend = attempts ? computeScoreTrend(attempts) : [];
  const readiness = overview ? computeReadinessIndex(overview) : 0;

  const submitted = attempts?.filter((a) => a.status === "SUBMITTED") ?? [];
  const totalCorrect = submitted.reduce((n, a) => n + (a.correct_count ?? 0), 0);
  const totalIncorrect = submitted.reduce((n, a) => n + (a.incorrect_count ?? 0), 0);
  const accuracyDenom = totalCorrect + totalIncorrect;
  const accuracyPct =
    accuracyDenom > 0 ? Math.round((100 * totalCorrect) / accuracyDenom) : null;
  const attemptedQs = totalCorrect + totalIncorrect;
  const todayFocus =
    (revisionDue && revisionDue[0]?.concept_name) ||
    (recommendations && recommendations[0]?.concept_name) ||
    null;
  const greetingName = user?.first_name ?? user?.display_name ?? "aspirant";
  const hasSubmitted = submitted.length > 0;
  const queuesLoading = revisionLoading || recommendationsLoading;
  const emailUnverified = Boolean(user && !user.email_verified);

  return (
    <StudentPage className="gap-7 lg:gap-10">
      {/* 1–2. Hero: context + primary CTA + readiness */}
      <section className="page-atmosphere relative overflow-hidden rounded-3xl border border-border/50 px-4 py-5 sm:px-8 sm:py-8">
        <div className="relative grid gap-5 sm:gap-6 lg:grid-cols-[minmax(0,1.35fr)_auto] lg:items-center lg:gap-10">
          <div className="min-w-0 space-y-3.5 sm:space-y-5">
            <PageHeader
              className="gap-1.5 sm:items-start sm:gap-2"
              eyebrow="NEET command center"
              title={isLoading ? "Loading…" : `Welcome back, ${greetingName}`}
              description={
                todayFocus
                  ? `Next focus: ${todayFocus}. Continue practice when you’re ready — published questions only.`
                  : "Calm, focused preparation. Start published NEET practice when you’re ready."
              }
            />
            <HeroPracticeCta />
          </div>

          <div className="flex flex-row items-center gap-4 justify-self-stretch sm:flex-col sm:items-center sm:gap-3 lg:justify-self-end">
            <SurfaceCard
              glass
              lift={false}
              accent="none"
              level="l2"
              className="shrink-0 p-3 sm:p-5 lg:p-6"
            >
              {overviewLoading ? (
                <Skeleton className="size-[112px] rounded-full sm:size-[140px]" />
              ) : (
                <div className="origin-center scale-90 sm:scale-100">
                  <ReadinessGauge value={readiness} label="NEET readiness" size={140} />
                </div>
              )}
            </SurfaceCard>
            {/* Metrics sit beside the gauge on mobile to shorten the first viewport */}
            <div className="grid min-w-0 flex-1 grid-cols-1 gap-2 sm:hidden">
              <MetricPill
                label="Accuracy"
                value={accuracyPct != null ? `${accuracyPct}%` : "—"}
              />
              <MetricPill label="Questions" value={String(attemptedQs)} />
              <MetricPill label="Sessions" value={String(submitted.length)} />
            </div>
            {!overviewLoading && overview && overview.length > 0 && (
              <p className="hidden max-w-[12rem] text-center text-xs text-muted-foreground sm:block">
                Blend of subject mastery and concept coverage from your attempts.
              </p>
            )}
          </div>
        </div>

        {/* Desktop/tablet metric strip — readiness lives in the gauge only */}
        <div className="relative mt-5 hidden grid-cols-3 gap-3 sm:mt-6 sm:grid">
          <MetricPill
            label="Accuracy"
            value={accuracyPct != null ? `${accuracyPct}%` : "—"}
          />
          <MetricPill label="Questions" value={String(attemptedQs)} />
          <MetricPill label="Sessions" value={String(submitted.length)} />
        </div>
      </section>

      {emailUnverified ? (
        <p
          className="flex flex-wrap items-center gap-x-2 gap-y-1 px-0.5 text-xs text-muted-foreground"
          role="status"
        >
          <span className="rounded-md border border-warning/30 bg-warning/10 px-2 py-0.5 font-medium text-warning-foreground">
            Email not verified
          </span>
          <span>
            You can keep practicing —{" "}
            <Link
              href="/verify-email"
              className="font-medium text-foreground underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              verify your email
            </Link>{" "}
            or use your account menu.
          </span>
        </p>
      ) : null}

      {/* Priorities */}
      <section className="space-y-4">
        <SectionHeader
          title="Today’s priorities"
          description="Revision due first, then high-yield recommendations — open the next concept when ready."
        />
        <div className="grid gap-5 lg:grid-cols-2">
          <SurfaceCard accent="top" theme="physics" glass={false} lift={false} level="l1">
            <SurfaceCardHeader>
              <SurfaceCardTitle>Revision due</SurfaceCardTitle>
              <SurfaceCardDescription>
                Concepts ready for another pass.
              </SurfaceCardDescription>
            </SurfaceCardHeader>
            <SurfaceCardContent className="flex flex-col gap-3">
              {queuesLoading && !revisionDue ? (
                <div className="space-y-3 py-2">
                  <Skeleton className="h-12 w-full rounded-xl" />
                  <Skeleton className="h-12 w-full rounded-xl" />
                </div>
              ) : revisionQuery.isError && !revisionDue ? (
                <FetchErrorAlert
                  testId="dashboard-revision-error"
                  message="Couldn’t load your revision queue."
                  onRetry={() => revisionQuery.refetch()}
                  isRetrying={revisionQuery.isFetching}
                />
              ) : !revisionDue || revisionDue.length === 0 ? (
                <EmptyState
                  icon={BookOpen}
                  title="Nothing due right now"
                  description="Keep practicing available concepts, or browse subjects to build your queue."
                  action={
                    <Link
                      href="/student/subjects"
                      className={cn(buttonVariants({ variant: "outline", size: "touch" }))}
                    >
                      Browse subjects
                    </Link>
                  }
                  className="py-8"
                />
              ) : (
                revisionDue.map((item, index) => (
                  <div
                    key={item.concept_id}
                    className={cn(
                      "flex items-center justify-between gap-3 rounded-xl border border-transparent px-2 py-2.5",
                      index === 0 && "border-subject-physics-border bg-subject-physics-muted/40",
                    )}
                  >
                    <div className="min-w-0">
                      {index === 0 ? (
                        <p className="mb-0.5 text-[0.65rem] font-medium uppercase tracking-[0.12em] text-subject-physics">
                          Next up
                        </p>
                      ) : null}
                      <p className="truncate text-sm font-medium">{item.concept_name}</p>
                      <p className="font-mono text-xs tabular-nums text-muted-foreground">
                        Score {item.mastery_score}
                        {item.published_question_count != null
                          ? ` · ${item.published_question_count} Q`
                          : ""}
                      </p>
                    </div>
                    <ConceptPracticeLink
                      conceptId={item.concept_id}
                      publishedCount={item.published_question_count}
                      label="Review"
                    />
                  </div>
                ))
              )}
            </SurfaceCardContent>
          </SurfaceCard>

          <SurfaceCard accent="top" theme="chemistry" glass={false} lift={false} level="l1">
            <SurfaceCardHeader>
              <SurfaceCardTitle>Recommended practice</SurfaceCardTitle>
              <SurfaceCardDescription>High-yield targets for today.</SurfaceCardDescription>
            </SurfaceCardHeader>
            <SurfaceCardContent className="flex flex-col gap-3">
              {queuesLoading && !recommendations ? (
                <div className="space-y-3 py-2">
                  <Skeleton className="h-12 w-full rounded-xl" />
                  <Skeleton className="h-12 w-full rounded-xl" />
                </div>
              ) : recommendationsQuery.isError && !recommendations ? (
                <FetchErrorAlert
                  testId="dashboard-recommendations-error"
                  message="Couldn’t load recommendations."
                  onRetry={() => recommendationsQuery.refetch()}
                  isRetrying={recommendationsQuery.isFetching}
                />
              ) : !recommendations || recommendations.length === 0 ? (
                <EmptyState
                  icon={Target}
                  title="No recommendations yet"
                  description="Once you practice a few concepts, we’ll surface what to do next."
                  action={
                    <Link
                      href="/student/practice"
                      className={cn(buttonVariants({ variant: "outline", size: "touch" }))}
                    >
                      Open practice arena
                    </Link>
                  }
                  className="py-8"
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
                      label="Practice"
                    />
                  </div>
                ))
              )}
            </SurfaceCardContent>
          </SurfaceCard>
        </div>
      </section>

      {/* Subject performance */}
      <section className="space-y-4">
        <SectionHeader
          title="Subject performance"
          description="Physics, Chemistry, Botany, and Zoology — compare mastery at a glance."
          actions={
            <Link
              href="/student/analytics"
              className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-primary outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              Full progress
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          }
        />
        <SurfaceCard accent="none" glass={false} lift={false} level="l1">
          <SurfaceCardContent className="flex flex-col gap-3 py-4 sm:gap-4 sm:py-5">
            {overviewLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-20 w-full rounded-2xl" />
                <Skeleton className="h-20 w-full rounded-2xl" />
                <Skeleton className="h-20 w-full rounded-2xl" />
              </div>
            ) : overviewQuery.isError && !overview ? (
              <FetchErrorAlert
                testId="dashboard-overview-error"
                message="Couldn’t load subject performance."
                onRetry={() => overviewQuery.refetch()}
                isRetrying={overviewQuery.isFetching}
              />
            ) : !overview || overview.length === 0 ? (
              <EmptyState
                title="No mastery data yet"
                description="Browse subjects and start practicing to build your map."
                action={
                  <Link
                    href="/student/subjects"
                    className={cn(buttonVariants({ variant: "outline", size: "touch" }))}
                  >
                    Browse subjects
                  </Link>
                }
                className="py-8"
              />
            ) : (
              overview.map((s) => (
                <SubjectMasteryRow
                  key={s.subject_id}
                  subjectId={s.subject_id}
                  subjectName={s.subject_name}
                  conceptsAttempted={s.concepts_attempted}
                  conceptsTotal={s.concepts_total}
                  averageScore={s.average_score}
                />
              ))
            )}
          </SurfaceCardContent>
        </SurfaceCard>
      </section>

      {/* Recent activity */}
      <section className="space-y-4">
        <SectionHeader
          title="Recent activity"
          description="Your practice trail and accuracy over submitted sessions."
        />
        <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
          <SurfaceCard accent="none" glass={false} lift={false} level="l1">
            <SurfaceCardHeader>
              <SurfaceCardTitle>Activity</SurfaceCardTitle>
              <SurfaceCardDescription>Last 28 days from real attempts.</SurfaceCardDescription>
            </SurfaceCardHeader>
            <SurfaceCardContent>
              {attemptsLoading ? (
                <Skeleton className="h-28 w-full rounded-xl" />
              ) : attemptsQuery.isError && !attempts ? (
                <FetchErrorAlert
                  testId="dashboard-attempts-error"
                  message="Couldn’t load recent activity."
                  onRetry={() => attemptsQuery.refetch()}
                  isRetrying={attemptsQuery.isFetching}
                />
              ) : (
                <StreakHeatmap attempts={attempts} />
              )}
            </SurfaceCardContent>
          </SurfaceCard>

          {hasSubmitted ? (
            <SurfaceCard accent="none" glass={false} lift={false} level="l1">
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
          ) : (
            <SurfaceCard accent="none" glass={false} lift={false} level="l1">
              <SurfaceCardContent className="flex h-full min-h-[10rem] flex-col justify-center py-8">
                <EmptyState
                  title="No submitted sessions yet"
                  description="Complete a practice or mock to unlock your accuracy trend."
                  action={
                    <Link
                      href="/student/practice"
                      className={cn(buttonVariants({ variant: "outline", size: "touch" }))}
                    >
                      Start practicing
                    </Link>
                  }
                  className="border-0 py-2"
                />
              </SurfaceCardContent>
            </SurfaceCard>
          )}
        </div>
      </section>

      {/* Secondary actions */}
      <section className="space-y-4">
        <SectionHeader
          title="More ways to prepare"
          description="Subjects, mocks, flashcards, and the question bank."
        />
        <QuickLaunchHub />
      </section>
    </StudentPage>
  );
}
