"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AiTutorBox } from "@/components/ai-tutor-box";
import { academicApi } from "@/features/academic/api";
import { cmsApi, type ConceptNoteBody, type QuestionBody } from "@/features/cms/api";

export default function ConceptDetailPage() {
  const { conceptId } = useParams<{ conceptId: string }>();
  const { data: concept, isLoading } = useQuery({
    queryKey: ["academic", "concept", conceptId],
    queryFn: () => academicApi.concept(conceptId),
  });
  const { data: content } = useQuery({
    queryKey: ["cms", "published", conceptId],
    queryFn: () => cmsApi.publishedForConcept(conceptId),
  });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }
  if (!concept) return null;

  const notes = content?.filter((c) => c.content_type === "CONCEPT_NOTE") ?? [];
  const questions = content?.filter((c) => c.content_type === "QUESTION") ?? [];

  return (
    <main className="flex flex-1 justify-center px-6 py-12">
      <div className="flex w-full max-w-2xl flex-col gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>{concept.name}</CardTitle>
              <Badge variant="outline">{concept.difficulty}</Badge>
            </div>
            {concept.ncert_reference && <CardDescription>{concept.ncert_reference}</CardDescription>}
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{concept.summary}</p>
          </CardContent>
        </Card>

        {notes.map((item) => {
          const body = item.latest_version?.body as unknown as ConceptNoteBody | undefined;
          return (
            <Card key={item.id}>
              <CardHeader>
                <CardTitle className="text-base">{item.title}</CardTitle>
                {body?.ncert_ref && <CardDescription>{body.ncert_ref}</CardDescription>}
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                <p className="text-sm">{body?.summary}</p>
                {!!body?.sections?.length && (
                  <ul className="list-inside list-disc text-sm text-muted-foreground">
                    {body.sections.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          );
        })}

        {questions.map((item) => {
          const body = item.latest_version?.body as unknown as QuestionBody | undefined;
          return (
            <Card key={item.id}>
              <CardHeader>
                <CardTitle className="text-base">Practice question</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                <p className="text-sm">{body?.stem}</p>
                <ul className="flex flex-col gap-1 text-sm">
                  {body?.options.map((o) => (
                    <li key={o.label} className={o.label === body.correct_option ? "font-medium" : ""}>
                      {o.label}. {o.text} {o.label === body.correct_option && "✓"}
                    </li>
                  ))}
                </ul>
                <p className="text-sm text-muted-foreground">{body?.explanation}</p>
              </CardContent>
            </Card>
          );
        })}

        {notes.length === 0 && questions.length === 0 && (
          <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
            No published content for this concept yet — visit /admin/content to author some.
          </p>
        )}

        <AiTutorBox conceptId={conceptId} />
      </div>
    </main>
  );
}
