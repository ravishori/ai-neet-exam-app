"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Layers } from "lucide-react";

import {
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { academicApi } from "@/features/academic/api";

export default function SubjectChaptersPage() {
  const { subjectId } = useParams<{ subjectId: string }>();

  const { data: subject } = useQuery({
    queryKey: ["academic", "subject", subjectId],
    queryFn: () => academicApi.subject(subjectId),
  });
  const { data: chapters, isLoading } = useQuery({
    queryKey: ["academic", "chapters", subjectId],
    queryFn: () => academicApi.chapters(subjectId),
  });

  return (
    <StudentPage width="lg">
      <PageHeader
        eyebrow={subject?.name ?? "Subject"}
        title="Chapters"
        description="Open a chapter to browse topics and concepts."
      />

      {isLoading ? (
        <div className="grid gap-3" aria-busy="true">
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
        </div>
      ) : !chapters?.length ? (
        <EmptyState icon={Layers} title="No chapters yet" description="Chapters for this subject are not available yet." />
      ) : (
        <div className="grid gap-3">
          {chapters.map((chapter) => (
            <Link key={chapter.id} href={`/student/chapters/${chapter.id}`} className="block">
              <SurfaceCard subject={subject?.name} accent="left">
                <SurfaceCardHeader className="flex-row items-center justify-between space-y-0 pb-4">
                  <div className="min-w-0">
                    <SurfaceCardTitle className="text-base">{chapter.name}</SurfaceCardTitle>
                    <SurfaceCardDescription>Chapter</SurfaceCardDescription>
                  </div>
                  {chapter.neet_weightage_percent != null && (
                    <Badge variant="secondary">{chapter.neet_weightage_percent}% weightage</Badge>
                  )}
                </SurfaceCardHeader>
              </SurfaceCard>
            </Link>
          ))}
        </div>
      )}
    </StudentPage>
  );
}
