"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
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

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 px-6 py-10">
      <h1 className="mb-6 text-xl font-semibold">{subject?.name ?? "Chapters"}</h1>
      <div className="grid gap-3">
        {chapters?.map((chapter) => (
          <Link key={chapter.id} href={`/student/chapters/${chapter.id}`}>
            <Card className="transition-colors hover:bg-muted">
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base">{chapter.name}</CardTitle>
                {chapter.neet_weightage_percent != null && (
                  <Badge variant="secondary">{chapter.neet_weightage_percent}% weightage</Badge>
                )}
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  );
}
