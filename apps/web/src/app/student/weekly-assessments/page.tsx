"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { CalendarClock, Sparkles, Target, Timer, TrendingUp } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { ApiError } from "@/lib/api-client";
import { weeklyRevisionsApi, type WeeklyRevisionCurrent } from "@/features/weekly-assessments/api";

function statusBadge(status: WeeklyRevisionCurrent["status"]) {
  switch (status) {
    case "RECOMMENDED":
      return <Badge className="bg-primary/15 text-primary">Recommended</Badge>;
    case "IN_PROGRESS":
      return <Badge className="bg-warning/15 text-warning-foreground">In progress</Badge>;
    case "COMPLETED":
      return <Badge className="bg-success/15 text-success">Completed</Badge>;
    case "UNAVAILABLE":
      return <Badge className="bg-muted text-muted-foreground">Unavailable this week</Badge>;
  }
}

function coldStartHint(rec: WeeklyRevisionCurrent) {
  if (rec.reason?.cold_start) {
    return "We haven’t seen much practice history yet — this first plan covers broad chapters to help us calibrate.";
  }
  return "Focused on your recently studied chapters, with retention questions from earlier weeks and extra practice on your weak areas.";
}

export default function WeeklyAssessmentsPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["weekly-revision", "current"],
    queryFn: weeklyRevisionsApi.getCurrent,
    staleTime: 60_000,
  });

  const start = useMutation({
    mutationFn: weeklyRevisionsApi.startCurrent,
    onSuccess: (data) => {
      qc.setQueryData(["weekly-revision", "current"], (old: WeeklyRevisionCurrent | undefined) =>
        old ? { ...old, status: "IN_PROGRESS" } : old,
      );
      router.push(`/student/attempts/${data.attempt_id}`);
    },
  });

  const errorMessage =
    start.error instanceof ApiError
      ? start.error.message
      : start.error
        ? "Could not start this week's revision"
        : null;

  return (
    <StudentPage>
      <PageHeader
        eyebrow="Weekly revision"
        title="Your Weekly Revision Assessment"
        description="A personalised recap the platform builds for you every week — recent chapters plus retention practice, with a nudge on weak topics."
      />

      {query.isPending && (
        <div className="grid gap-4">
          <Skeleton className="h-56 w-full" />
        </div>
      )}

      {query.isError && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>Could not load this week&apos;s revision plan. Try again in a moment.</AlertDescription>
        </Alert>
      )}

      {errorMessage && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      )}

      {query.isSuccess && query.data.status === "UNAVAILABLE" && (
        <SurfaceCard>
          <SurfaceCardHeader>
            <div className="flex items-start justify-between gap-3">
              <SurfaceCardTitle>Not enough questions yet</SurfaceCardTitle>
              {statusBadge(query.data.status)}
            </div>
            <SurfaceCardDescription>
              We could not build this week&apos;s revision from the currently published pool. Your instructor may
              be adding new material — check back after any recent uploads.
            </SurfaceCardDescription>
          </SurfaceCardHeader>
          <SurfaceCardContent>
            {query.data.reason?.unavailable_reasons?.length ? (
              <ul className="ml-5 list-disc space-y-1 text-caption">
                {query.data.reason.unavailable_reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            ) : null}
          </SurfaceCardContent>
        </SurfaceCard>
      )}

      {query.isSuccess && query.data.status !== "UNAVAILABLE" && (
        <WeeklyRevisionCard
          rec={query.data}
          onStart={() => start.mutate()}
          starting={start.isPending}
        />
      )}
    </StudentPage>
  );
}

export function WeeklyRevisionCard({
  rec,
  onStart,
  starting,
}: {
  rec: WeeklyRevisionCurrent;
  onStart: () => void;
  starting: boolean;
}) {
  const primaryLabel =
    rec.status === "COMPLETED"
      ? "Completed for this week"
      : rec.status === "IN_PROGRESS"
        ? "Resume assessment"
        : "Take Weekly Assessment";
  const disabled = rec.status === "COMPLETED" || rec.status === "UNAVAILABLE" || starting;

  return (
    <SurfaceCard>
      <SurfaceCardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <SurfaceCardTitle>Week {rec.iso_week} · Recommended for you</SurfaceCardTitle>
            <SurfaceCardDescription>{coldStartHint(rec)}</SurfaceCardDescription>
          </div>
          {statusBadge(rec.status)}
        </div>
      </SurfaceCardHeader>
      <SurfaceCardContent className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="flex items-center gap-2 text-body">
            <TrendingUp className="size-4 text-muted-foreground" aria-hidden="true" />
            <span className="font-medium">{rec.total_questions} questions</span>
          </div>
          <div className="flex items-center gap-2 text-body">
            <Timer className="size-4 text-muted-foreground" aria-hidden="true" />
            <span>
              {rec.estimated_duration_minutes} min · +{rec.marks_per_question} / -{rec.negative_marks_per_question}
            </span>
          </div>
          <div className="flex items-center gap-2 text-body">
            <CalendarClock className="size-4 text-muted-foreground" aria-hidden="true" />
            <span>Refreshes every ISO week</span>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          {rec.blueprint.map((bucket) => (
            <div key={bucket.label} className="rounded-lg border p-3">
              <p className="text-meta">{bucket.label}</p>
              <p className="text-h3 mt-1">{bucket.quota} questions</p>
              <p className="text-caption mt-1">
                {bucket.recent_quota} recent · {bucket.previous_quota} retention
                {bucket.weak_chapter_count > 0 && ` · ${bucket.weak_chapter_count} weak-topic chapters`}
              </p>
              {bucket.used_cold_start && (
                <p className="text-caption mt-1 text-muted-foreground">
                  <Sparkles className="inline size-3.5" aria-hidden="true" /> cold-start plan
                </p>
              )}
            </div>
          ))}
        </div>

        <div className="flex items-start gap-2 rounded-md bg-muted/40 p-3 text-caption">
          <Target className="mt-0.5 size-4 text-muted-foreground" aria-hidden="true" />
          <span>
            Recommended, not required. Skipping this week won&apos;t affect anything — the plan refreshes next week.
          </span>
        </div>

        <div>
          <Button
            onClick={onStart}
            disabled={disabled}
            aria-disabled={disabled}
            data-testid="weekly-revision-start"
          >
            {starting ? "Starting…" : primaryLabel}
          </Button>
        </div>
      </SurfaceCardContent>
    </SurfaceCard>
  );
}

export function WeeklyRevisionEmpty() {
  return (
    <EmptyState
      icon={CalendarClock}
      title="Your first weekly plan will appear soon"
      description="Once we can see any recent practice or newly published questions, your weekly revision will show up here."
    />
  );
}
