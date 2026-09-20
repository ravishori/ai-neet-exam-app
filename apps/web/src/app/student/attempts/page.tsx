"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { assessmentApi } from "@/features/assessment/api";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function AttemptsHistoryPage() {
  const { data: attempts, isLoading } = useQuery({
    queryKey: ["assessment", "attempts"],
    queryFn: assessmentApi.listAttempts,
  });

  return (
    <StudentPage width="lg">
      <PageHeader
        eyebrow="History"
        title="My attempts"
        description="Review past practice and mock sessions — open any attempt to see score and mistakes."
      />

      {isLoading ? (
        <div className="grid gap-3" aria-busy="true">
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
        </div>
      ) : !attempts?.length ? (
        <EmptyState
          icon={History}
          title="No practice attempts yet"
          description="Start your first practice session to begin tracking your progress."
          action={
            <Link href="/student/practice" className={cn(buttonVariants({ size: "touch" }))}>
              Start Practice
            </Link>
          }
        />
      ) : (
        <div className="grid gap-3">
          {attempts.map((a) => (
            <Link key={a.id} href={`/student/attempts/${a.id}`} className="block outline-none focus-visible:ring-2 focus-visible:ring-ring/50 rounded-2xl">
              <SurfaceCard accent="none" lift>
                <SurfaceCardHeader className="flex-row items-center justify-between space-y-0 pb-5">
                  <div className="min-w-0">
                    <SurfaceCardTitle className="text-base">
                      {new Date(a.started_at).toLocaleString()}
                    </SurfaceCardTitle>
                    <SurfaceCardDescription>
                      {a.status === "SUBMITTED" && a.score != null
                        ? `Score ${a.score}`
                        : "In progress — continue where you left off"}
                    </SurfaceCardDescription>
                  </div>
                  <Badge variant={a.status === "SUBMITTED" ? "default" : "secondary"}>{a.status}</Badge>
                </SurfaceCardHeader>
              </SurfaceCard>
            </Link>
          ))}
        </div>
      )}
    </StudentPage>
  );
}
