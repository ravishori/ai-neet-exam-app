"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import {
  PageHeader,
  ReadinessGauge,
  StudentPage,
  computeReadinessIndex,
  SubjectChip,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { MasteryBar } from "@/components/mastery-badge";
import { ScoreTrendChart } from "@/components/score-trend-chart";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { assessmentApi } from "@/features/assessment/api";
import { computeScoreTrend } from "@/features/assessment/analytics";
import { learningApi } from "@/features/learning/api";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BarChart3 } from "lucide-react";

function subjectWeaknessBars(overview: { subject_name: string; average_score: number; concepts_attempted: number; concepts_total: number }[]) {
  return [...overview].sort((a, b) => a.average_score - b.average_score);
}

export default function StudentAnalyticsPage() {
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ["learning", "overview"],
    queryFn: learningApi.overview,
  });
  const { data: attempts, isLoading: attemptsLoading } = useQuery({
    queryKey: ["assessment", "attempts"],
    queryFn: assessmentApi.listAttempts,
  });

  const readiness = overview ? computeReadinessIndex(overview) : 0;
  const trend = attempts ? computeScoreTrend(attempts) : [];
  const submitted = attempts?.filter((a) => a.status === "SUBMITTED") ?? [];
  const avgAccuracy =
    trend.length > 0 ? Math.round(trend.reduce((s, p) => s + p.score, 0) / trend.length) : null;
  const weakSubjects = overview ? subjectWeaknessBars(overview) : [];

  return (
    <StudentPage width="xl" className="gap-8">
      <PageHeader
        eyebrow="Diagnostic scorecard"
        title="Analytics"
        description="Scores below are computed from your real practice and mock attempts — not a simulated NEET percentile model. Use them to prioritize weak subjects before you sit a full paper."
      />

      <div className="grid gap-6 lg:grid-cols-[auto_1fr]">
        <SurfaceCard glass lift={false} accent="none" className="justify-self-center p-6">
          {overviewLoading ? <Skeleton className="size-[140px] rounded-full" /> : <ReadinessGauge value={readiness} label="Readiness index" />}
        </SurfaceCard>

        <div className="grid gap-4 sm:grid-cols-3">
          <SurfaceCard accent="none">
            <SurfaceCardContent className="pt-5">
              <p className="text-xs font-medium text-muted-foreground">Submitted attempts</p>
              <p className="mt-1 font-mono text-3xl font-semibold tabular-nums">{submitted.length}</p>
            </SurfaceCardContent>
          </SurfaceCard>
          <SurfaceCard accent="none">
            <SurfaceCardContent className="pt-5">
              <p className="text-xs font-medium text-muted-foreground">Avg accuracy (trend)</p>
              <p className="mt-1 font-mono text-3xl font-semibold tabular-nums">
                {avgAccuracy != null ? `${avgAccuracy}%` : "—"}
              </p>
            </SurfaceCardContent>
          </SurfaceCard>
          <SurfaceCard accent="none">
            <SurfaceCardContent className="pt-5">
              <p className="text-xs font-medium text-muted-foreground">Subjects tracked</p>
              <p className="mt-1 font-mono text-3xl font-semibold tabular-nums">{overview?.length ?? 0}</p>
            </SurfaceCardContent>
          </SurfaceCard>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <SurfaceCard accent="top" theme="biology">
          <SurfaceCardHeader>
            <SurfaceCardTitle>Subject weakness map</SurfaceCardTitle>
            <SurfaceCardDescription>Lowest mastery first — focus remedy practice here.</SurfaceCardDescription>
          </SurfaceCardHeader>
          <SurfaceCardContent className="flex flex-col gap-4">
            {overviewLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : weakSubjects.length === 0 ? (
              <EmptyState
                icon={BarChart3}
                title="No subject data yet"
                description="Start a practice session to populate this map."
                action={
                  <Link href="/student/practice" className={cn(buttonVariants({ size: "sm" }), "min-h-11")}>
                    Open practice
                  </Link>
                }
              />
            ) : (
              weakSubjects.map((s) => (
                <div key={s.subject_name} className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <SubjectChip subject={s.subject_name} />
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

        <SurfaceCard accent="top" theme="physics">
          <SurfaceCardHeader>
            <SurfaceCardTitle>Accuracy trend</SurfaceCardTitle>
            <SurfaceCardDescription>
              <Link href="/student/attempts" className="hover:underline">
                Attempt history
              </Link>
            </SurfaceCardDescription>
          </SurfaceCardHeader>
          <SurfaceCardContent>
            {attemptsLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : trend.length === 0 ? (
              <EmptyState
                icon={BarChart3}
                title="No accuracy trend yet"
                description="Submit at least one attempt to see your accuracy trail."
              />
            ) : (
              <ScoreTrendChart points={trend} />
            )}
          </SurfaceCardContent>
        </SurfaceCard>
      </div>

      <SurfaceCard accent="none" className="border border-dashed">
        <SurfaceCardContent className="flex flex-col gap-2 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-heading text-sm font-semibold">AI remedy plan</p>
            <p className="text-sm text-muted-foreground">
              Generate a weekly focus list from your scores and weak concepts.
            </p>
          </div>
          <Link
            href="/student/study-plan"
            className="inline-flex h-9 items-center justify-center rounded-lg ai-gradient px-4 text-sm font-medium text-white shadow-md"
          >
            Open study coach
          </Link>
        </SurfaceCardContent>
      </SurfaceCard>
    </StudentPage>
  );
}
