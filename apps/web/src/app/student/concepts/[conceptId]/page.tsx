"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AiTutorBox } from "@/components/ai-tutor-box";
import { MasteryBadge, MasteryBar } from "@/components/mastery-badge";
import { academicApi } from "@/features/academic/api";
import { cmsApi, type ConceptNoteBody, type QuestionBody } from "@/features/cms/api";
import { learningApi } from "@/features/learning/api";
import { usersApi } from "@/features/users/api";

export default function ConceptDetailPage() {
  const { conceptId } = useParams<{ conceptId: string }>();
  const { data: concept, isLoading } = useQuery({
    queryKey: ["academic", "concept", conceptId],
    queryFn: () => academicApi.concept(conceptId),
  });
  const { data: profile } = useQuery({ queryKey: ["users", "me"], queryFn: usersApi.me });
  const { data: content } = useQuery({
    queryKey: ["cms", "published", conceptId, profile?.preferred_language],
    queryFn: () => cmsApi.publishedForConcept(conceptId, profile?.preferred_language),
    enabled: !!profile,
  });
  const { data: mastery } = useQuery({
    queryKey: ["learning", "concept-mastery", conceptId],
    queryFn: () => learningApi.conceptMastery(conceptId),
  });
  const { data: microBreakdown } = useQuery({
    queryKey: ["learning", "micro-competency-breakdown", conceptId],
    queryFn: () => learningApi.microCompetencyBreakdown(conceptId),
  });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }
  if (!concept) return null;

  const notes = content?.items.filter((c) => c.content_type === "CONCEPT_NOTE") ?? [];
  const questions = content?.items.filter((c) => c.content_type === "QUESTION") ?? [];

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

        {mastery && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Your mastery</CardTitle>
                <MasteryBadge level={mastery.mastery_level} />
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <MasteryBar score={mastery.mastery_score} />
              <p className="text-xs text-muted-foreground">
                {mastery.attempts_count === 0
                  ? "Answer a practice question on this concept to start tracking mastery."
                  : `${mastery.correct_count}/${mastery.attempts_count} correct across your attempts.`}
              </p>
            </CardContent>
          </Card>
        )}

        {!!microBreakdown?.length && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Mastery by micro-competency</CardTitle>
              <CardDescription>How you&apos;re doing on each specific skill within this concept.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {microBreakdown.map((mc) => (
                <div key={mc.micro_competency_id} className="flex flex-col gap-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm">{mc.name}</p>
                    <MasteryBadge level={mc.mastery_level} />
                  </div>
                  <MasteryBar score={mc.mastery_score} />
                  <p className="text-xs text-muted-foreground">
                    {mc.attempts_count === 0
                      ? "No attempts yet."
                      : `${mc.correct_count}/${mc.attempts_count} correct.`}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {content?.languageFallback && (
          <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
            Showing English — this concept hasn&apos;t been translated to {content.language === "hi" ? "Hindi" : content.language} yet.
          </p>
        )}

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
