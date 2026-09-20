"use client";

import { CalendarClock, Sparkles, Target, Timer, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";

import type { WeeklyRevisionCurrent } from "@/features/weekly-assessments/api";

/** Non-route module — extracted from
 * `src/app/student/weekly-assessments/page.tsx` because the Next.js
 * App Router only permits the default page component and a fixed set of
 * route-segment options as named exports from `page.tsx`. Any other
 * named export fails production type validation with
 * `"<Name>" is not a valid Page export field.`
 */

export function statusBadge(status: WeeklyRevisionCurrent["status"]) {
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

export function coldStartHint(rec: WeeklyRevisionCurrent): string {
  if (rec.reason?.cold_start) {
    return "We haven’t seen much practice history yet — this first plan covers broad chapters to help us calibrate.";
  }
  return "Focused on your recently studied chapters, with retention questions from earlier weeks and extra practice on your weak areas.";
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
