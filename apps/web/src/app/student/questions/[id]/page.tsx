"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { questionsApi } from "@/features/questions/api";
import { ApiError } from "@/lib/api-client";

function DifficultyBadge({ difficulty }: { difficulty: string | null }) {
  if (!difficulty) return null;
  return (
    <Badge variant={difficulty === "hard" ? "destructive" : difficulty === "easy" ? "secondary" : "outline"}>{difficulty}</Badge>
  );
}

export default function QuestionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const query = useQuery({
    queryKey: ["question", id],
    queryFn: () => questionsApi.get(id),
    retry: (failureCount, error) => error instanceof ApiError && error.status === 404 ? false : failureCount < 2,
  });

  const notFound = query.isError && query.error instanceof ApiError && query.error.status === 404;

  return (
    <main className="flex flex-1 justify-center px-4 py-8 sm:px-6 sm:py-12">
      <div className="flex w-full max-w-2xl flex-col gap-4">
        <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
          <Link href="/student/questions" className="underline-offset-4 hover:underline focus-visible:underline">
            &larr; Back to questions
          </Link>
        </nav>

        {query.isLoading && (
          <div className="flex flex-col gap-3" aria-busy="true" aria-live="polite">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-40 w-full" />
          </div>
        )}

        {notFound && (
          <EmptyState
            title="Question not found"
            description="It may have been unpublished, or the link is incorrect."
          />
        )}

        {query.data && (
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <CardTitle className="text-lg font-semibold leading-snug">
                  <h1>{query.data.stem}</h1>
                </CardTitle>
                <DifficultyBadge difficulty={query.data.difficulty} />
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              {query.data.images.length > 0 && (
                <div className="flex flex-col gap-3">
                  {query.data.images.map((img) => (
                    <img
                      key={img.id}
                      src={`/api/visual-assets/${img.id}`}
                      alt={img.alt_text ?? "Diagram accompanying this question"}
                      width={img.width_px ?? undefined}
                      height={img.height_px ?? undefined}
                      className="h-auto max-w-full rounded-md border border-border"
                    />
                  ))}
                </div>
              )}

              <fieldset>
                <legend className="sr-only">Answer options</legend>
                <ul className="flex flex-col gap-2 text-sm">
                  {query.data.options.map((opt) => (
                    <li
                      key={opt.label}
                      className="rounded-md border border-border px-3 py-2"
                    >
                      <span className="font-medium text-foreground">{opt.label}.</span> {opt.text}
                    </li>
                  ))}
                </ul>
              </fieldset>

              <div className="flex flex-wrap items-center gap-1.5" aria-label="Question metadata">
                {query.data.subject && <Badge variant="outline">{query.data.subject.name}</Badge>}
                {query.data.chapter && <Badge variant="outline">{query.data.chapter.name}</Badge>}
                {query.data.topic && <Badge variant="outline">{query.data.topic.name}</Badge>}
                {query.data.concept && <Badge variant="outline">{query.data.concept.name}</Badge>}
                {query.data.bloom_level && <Badge variant="ghost">{query.data.bloom_level}</Badge>}
                {query.data.pyq_year && <Badge variant="ghost">PYQ {query.data.pyq_year}</Badge>}
              </div>

              <p className="text-xs text-muted-foreground">
                This is a preview — the answer is revealed after you practice this question in a timed or untimed session.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}
