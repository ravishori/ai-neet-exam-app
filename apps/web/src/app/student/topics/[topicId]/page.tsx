"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Shapes } from "lucide-react";

import {
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { MasteryBadge } from "@/components/mastery-badge";
import { academicApi } from "@/features/academic/api";
import { learningApi } from "@/features/learning/api";

export default function TopicConceptsPage() {
  const { topicId } = useParams<{ topicId: string }>();

  const { data: topic } = useQuery({
    queryKey: ["academic", "topic", topicId],
    queryFn: () => academicApi.topic(topicId),
  });
  const { data: concepts, isLoading } = useQuery({
    queryKey: ["academic", "concepts", topicId],
    queryFn: () => academicApi.concepts(topicId),
  });
  const { data: mastery } = useQuery({
    queryKey: ["learning", "topic-mastery", topicId],
    queryFn: () => learningApi.topicMastery(topicId),
  });
  const levelByConceptId = new Map(mastery?.concepts.map((c) => [c.concept_id, c.mastery_level]));

  return (
    <StudentPage width="lg">
      <PageHeader
        eyebrow={topic?.name ?? "Topic"}
        title="Concepts"
        description={mastery ? `Topic average: ${mastery.average_score}%` : "Open a concept for notes, flashcards, and practice."}
      />

      {isLoading ? (
        <div className="grid gap-3" aria-busy="true">
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
        </div>
      ) : !concepts?.length ? (
        <EmptyState icon={Shapes} title="No concepts yet" description="Concepts for this topic are not available yet." />
      ) : (
        <div className="grid gap-3">
          {concepts.map((concept) => (
            <Link key={concept.id} href={`/student/concepts/${concept.id}`} className="block">
              <SurfaceCard accent="left">
                <SurfaceCardHeader className="flex-row items-center justify-between space-y-0 pb-4">
                  <SurfaceCardTitle className="text-base">{concept.name}</SurfaceCardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{concept.difficulty}</Badge>
                    {levelByConceptId.get(concept.id) && <MasteryBadge level={levelByConceptId.get(concept.id)!} />}
                  </div>
                </SurfaceCardHeader>
              </SurfaceCard>
            </Link>
          ))}
        </div>
      )}
    </StudentPage>
  );
}
