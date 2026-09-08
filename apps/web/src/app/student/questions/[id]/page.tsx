"use client";

import { Loader2, Play } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { questionsApi, type QuestionProvenance } from "@/features/questions/api";
import { practiceStartMessage, useStartPractice } from "@/features/assessment/use-start-practice";
import { ApiError } from "@/lib/api-client";

function DifficultyBadge({ difficulty }: { difficulty: string | null }) {
  if (!difficulty) return null;
  return (
    <Badge variant={difficulty === "hard" ? "destructive" : difficulty === "easy" ? "secondary" : "outline"}>{difficulty}</Badge>
  );
}

function ProvenanceCard({
  provenance,
  classLevel,
  ncertReference,
}: {
  provenance: QuestionProvenance;
  classLevel: "11" | "12" | null;
  ncertReference: string | null;
}) {
  // Read-only — every field renders only if the DB actually populated it.
  const rows: Array<{ label: string; value: string }> = [];
  rows.push({ label: "Source", value: provenance.source.replace(/_/g, " ").toLowerCase() });
  if (classLevel) rows.push({ label: "Class", value: `Class ${classLevel}` });
  if (ncertReference) rows.push({ label: "NCERT reference (from concept)", value: ncertReference });
  if (provenance.ncert_reference_tag)
    rows.push({ label: "NCERT reference tag", value: provenance.ncert_reference_tag });
  if (provenance.ncert_verification_level)
    rows.push({ label: "NCERT verification level", value: provenance.ncert_verification_level });
  if (provenance.source_pdf) rows.push({ label: "Source PDF", value: provenance.source_pdf });
  if (provenance.model_used) rows.push({ label: "Model used", value: provenance.model_used });
  if (provenance.prompt_version) rows.push({ label: "Prompt version", value: provenance.prompt_version });
  if (provenance.confidence_score !== null && provenance.confidence_score !== undefined) {
    rows.push({ label: "Confidence", value: provenance.confidence_score.toFixed(2) });
  }
  if (provenance.knowledge_unit_id) rows.push({ label: "Knowledge unit", value: provenance.knowledge_unit_id });
  if (provenance.authored_at)
    rows.push({ label: "Authored at", value: new Date(provenance.authored_at).toLocaleString() });
  return (
    <Card className="border-border/60">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Provenance
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
          {rows.map((r) => (
            <div key={r.label} className="flex flex-col gap-0.5">
              <dt className="font-medium text-muted-foreground">{r.label}</dt>
              <dd className="break-words font-mono text-[11px] text-foreground/90">{r.value}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-[11px] text-muted-foreground">
          Source, alignment and verification are separate signals. &ldquo;NCERT source&rdquo; means the question was ingested
          from an NCERT PDF; a verification level only appears when the editorial pipeline actually recorded one — this app
          never claims &ldquo;NCERT verified&rdquo; unless that level is stored.
        </p>
      </CardContent>
    </Card>
  );
}

function PracticeThisConceptButton({ conceptId }: { conceptId: string | null }) {
  const start = useStartPractice();
  if (!conceptId) return null;
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <Button
        type="button"
        onClick={() => start.mutate({ scope_type: "CONCEPT", scope_id: conceptId })}
        disabled={start.isPending}
        aria-busy={start.isPending}
        className="gap-2"
      >
        {start.isPending ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            Starting practice…
          </>
        ) : (
          <>
            <Play className="size-4" aria-hidden />
            Practice this concept
          </>
        )}
      </Button>
      <p className="text-xs text-muted-foreground">
        Reuses the same practice engine as the dashboard&rsquo;s Practice Now — 30 published questions on this concept, no
        duplicate flow.
      </p>
      {start.isError && (
        <Alert variant="destructive" role="alert" className="sm:basis-full">
          <AlertDescription>{practiceStartMessage(start.error)}</AlertDescription>
        </Alert>
      )}
    </div>
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
                {query.data.class_level && <Badge variant="secondary">Class {query.data.class_level}</Badge>}
                {query.data.chapter && <Badge variant="outline">{query.data.chapter.name}</Badge>}
                {query.data.topic && <Badge variant="outline">{query.data.topic.name}</Badge>}
                {query.data.concept && <Badge variant="outline">{query.data.concept.name}</Badge>}
                {query.data.bloom_level && <Badge variant="ghost">{query.data.bloom_level}</Badge>}
                {query.data.pyq_year && <Badge variant="ghost">PYQ {query.data.pyq_year}</Badge>}
              </div>

              <PracticeThisConceptButton conceptId={query.data.concept?.id ?? null} />

              <ProvenanceCard
                provenance={query.data.provenance}
                classLevel={query.data.class_level}
                ncertReference={query.data.ncert_reference}
              />

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
