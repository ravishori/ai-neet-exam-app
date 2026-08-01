"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
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

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">{topic?.name ?? "Concepts"}</h1>
        {mastery && <p className="text-sm text-muted-foreground">Topic average: {mastery.average_score}%</p>}
      </div>
      <div className="grid gap-3">
        {concepts?.map((concept) => (
          <Link key={concept.id} href={`/student/concepts/${concept.id}`}>
            <Card className="transition-colors hover:bg-muted">
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base">{concept.name}</CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{concept.difficulty}</Badge>
                  {levelByConceptId.get(concept.id) && <MasteryBadge level={levelByConceptId.get(concept.id)!} />}
                </div>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  );
}
