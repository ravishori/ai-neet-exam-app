"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { academicApi } from "@/features/academic/api";

export default function ConceptDetailPage() {
  const { conceptId } = useParams<{ conceptId: string }>();
  const { data: concept, isLoading } = useQuery({
    queryKey: ["academic", "concept", conceptId],
    queryFn: () => academicApi.concept(conceptId),
  });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }
  if (!concept) return null;

  return (
    <main className="flex flex-1 justify-center px-6 py-12">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{concept.name}</CardTitle>
            <Badge variant="outline">{concept.difficulty}</Badge>
          </div>
          {concept.ncert_reference && <CardDescription>{concept.ncert_reference}</CardDescription>}
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">{concept.summary}</p>
          <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            Videos, notes, flashcards, and questions attach here once ECAEP (Sprint 3) and the
            Question Bank (Sprint 3–4) exist. The AI Tutor (Sprint 5) will cite this concept
            directly.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
