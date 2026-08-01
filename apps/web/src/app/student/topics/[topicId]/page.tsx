"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { academicApi } from "@/features/academic/api";

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

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 px-6 py-10">
      <h1 className="mb-6 text-xl font-semibold">{topic?.name ?? "Concepts"}</h1>
      <div className="grid gap-3">
        {concepts?.map((concept) => (
          <Link key={concept.id} href={`/student/concepts/${concept.id}`}>
            <Card className="transition-colors hover:bg-muted">
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base">{concept.name}</CardTitle>
                <Badge variant="outline">{concept.difficulty}</Badge>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  );
}
