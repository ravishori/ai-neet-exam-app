"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
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
import {
  WeeklyRevisionCard,
  statusBadge,
} from "@/features/weekly-assessments/weekly-revision-card";

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
