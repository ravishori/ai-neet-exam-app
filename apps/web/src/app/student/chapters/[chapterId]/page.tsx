"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Card, CardHeader, CardTitle } from "@/components/ui/card";
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

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 px-6 py-10">
      <h1 className="mb-6 text-xl font-semibold">{chapter?.name ?? "Topics"}</h1>
      {topics && topics.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No topics yet — this chapter is queued for content authoring (Sprint 3).
        </p>
      )}
      <div className="grid gap-3">
        {topics?.map((topic) => (
          <Link key={topic.id} href={`/student/topics/${topic.id}`}>
            <Card className="transition-colors hover:bg-muted">
              <CardHeader>
                <CardTitle className="text-base">{topic.name}</CardTitle>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  );
}
