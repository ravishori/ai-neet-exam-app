"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ListTree } from "lucide-react";

import {
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { academicApi } from "@/features/academic/api";

export default function ChapterTopicsPage() {
  const { chapterId } = useParams<{ chapterId: string }>();

  const { data: chapter } = useQuery({
    queryKey: ["academic", "chapter", chapterId],
    queryFn: () => academicApi.chapter(chapterId),
  });
  const { data: topics, isLoading } = useQuery({
    queryKey: ["academic", "topics", chapterId],
    queryFn: () => academicApi.topics(chapterId),
  });

  return (
    <StudentPage width="lg">
      <PageHeader
        eyebrow={chapter?.name ?? "Chapter"}
        title="Topics"
        description="Choose a topic to see concepts and start targeted practice."
      />

      {isLoading ? (
        <div className="grid gap-3" aria-busy="true">
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
        </div>
      ) : !topics?.length ? (
        <EmptyState
          icon={ListTree}
          title="No topics yet"
          description="This chapter is queued for content authoring."
        />
      ) : (
        <div className="grid gap-3">
          {topics.map((topic) => (
            <Link key={topic.id} href={`/student/topics/${topic.id}`} className="block">
              <SurfaceCard accent="left">
                <SurfaceCardHeader>
                  <SurfaceCardTitle className="text-base">{topic.name}</SurfaceCardTitle>
                  <SurfaceCardDescription>View concepts → practice</SurfaceCardDescription>
                </SurfaceCardHeader>
              </SurfaceCard>
            </Link>
          ))}
        </div>
      )}
    </StudentPage>
  );
}
