"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";

import {
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { AiTutorBox } from "@/components/ai-tutor-box";
import { ConceptPracticeQuestion } from "@/components/concept-practice-question";
import { FlipCard } from "@/components/flip-card";
import { MasteryBadge, MasteryBar } from "@/components/mastery-badge";
import { academicApi } from "@/features/academic/api";
import { cmsApi, type ConceptNoteBody, type FlashcardBody, type QuestionBody } from "@/features/cms/api";
import { practiceStartMessage, useStartPractice } from "@/features/assessment/use-start-practice";
import { learningApi } from "@/features/learning/api";
import { usersApi } from "@/features/users/api";

export default function ConceptDetailPage() {
  const { conceptId } = useParams<{ conceptId: string }>();
  const startPractice = useStartPractice();
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
    return (
      <StudentPage width="lg">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </StudentPage>
    );
  }
  if (!concept) return null;

  const notes = content?.items.filter((c) => c.content_type === "CONCEPT_NOTE") ?? [];
  const questions = content?.items.filter((c) => c.content_type === "QUESTION") ?? [];
  const flashcards = content?.items.filter((c) => c.content_type === "FLASHCARD") ?? [];

  return (
    <StudentPage width="lg">
      <PageHeader
        eyebrow="Concept"
        title={concept.name}
        description={concept.summary ?? undefined}
        actions={<Badge variant="outline">{concept.difficulty}</Badge>}
      />
      {concept.ncert_reference ? (
        <p className="text-xs text-muted-foreground">NCERT: {concept.ncert_reference}</p>
      ) : null}

      {mastery && (
        <SurfaceCard accent="top" theme="biology">
          <SurfaceCardHeader>
            <div className="flex items-center justify-between gap-2">
              <SurfaceCardTitle>Your mastery</SurfaceCardTitle>
              <MasteryBadge level={mastery.mastery_level} />
            </div>
          </SurfaceCardHeader>
          <SurfaceCardContent className="flex flex-col gap-2">
            <MasteryBar score={mastery.mastery_score} />
            <p className="text-xs text-muted-foreground">
              {mastery.attempts_count === 0
                ? "Answer a practice question on this concept to start tracking mastery."
                : `${mastery.correct_count}/${mastery.attempts_count} correct across your attempts.`}
            </p>
          </SurfaceCardContent>
        </SurfaceCard>
      )}

      {!!microBreakdown?.length && (
        <SurfaceCard accent="none">
          <SurfaceCardHeader>
            <SurfaceCardTitle>Mastery by micro-competency</SurfaceCardTitle>
            <SurfaceCardDescription>How you&apos;re doing on each specific skill within this concept.</SurfaceCardDescription>
          </SurfaceCardHeader>
          <SurfaceCardContent className="flex flex-col gap-3">
            {microBreakdown.map((mc) => (
              <div key={mc.micro_competency_id} className="flex flex-col gap-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm">{mc.name}</p>
                  <MasteryBadge level={mc.mastery_level} />
                </div>
                <MasteryBar score={mc.mastery_score} />
                <p className="text-xs text-muted-foreground">
                  {mc.attempts_count === 0 ? "No attempts yet." : `${mc.correct_count}/${mc.attempts_count} correct.`}
                </p>
              </div>
            ))}
          </SurfaceCardContent>
        </SurfaceCard>
      )}

      {content?.languageFallback && (
        <p className="rounded-xl border border-dashed p-3 text-xs text-muted-foreground">
          Showing English — this concept hasn&apos;t been translated to{" "}
          {content.language === "hi" ? "Hindi" : content.language} yet.
        </p>
      )}

      {notes.map((item) => {
        const body = item.latest_version?.body as unknown as ConceptNoteBody | undefined;
        return (
          <SurfaceCard key={item.id} accent="none">
            <SurfaceCardHeader>
              <SurfaceCardTitle>{item.title}</SurfaceCardTitle>
              {body?.ncert_ref && <SurfaceCardDescription>{body.ncert_ref}</SurfaceCardDescription>}
            </SurfaceCardHeader>
            <SurfaceCardContent className="flex flex-col gap-2">
              <p className="text-sm">{body?.summary}</p>
              {!!body?.sections?.length && (
                <ul className="list-inside list-disc text-sm text-muted-foreground">
                  {body.sections.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              )}
            </SurfaceCardContent>
          </SurfaceCard>
        );
      })}

      {!!flashcards.length && (
        <SurfaceCard accent="top" theme="chemistry">
          <SurfaceCardHeader>
            <SurfaceCardTitle>Flashcards</SurfaceCardTitle>
            <SurfaceCardDescription>Quick revision — tap a card to flip it.</SurfaceCardDescription>
          </SurfaceCardHeader>
          <SurfaceCardContent>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {flashcards.map((item) => {
                const body = item.latest_version?.body as unknown as FlashcardBody | undefined;
                return <FlipCard key={item.id} front={body?.front ?? ""} back={body?.back ?? ""} imageUrl={body?.image_url} />;
              })}
            </div>
          </SurfaceCardContent>
        </SurfaceCard>
      )}

      {!!questions.length && (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            className="min-h-11"
            disabled={startPractice.isPending}
            onClick={() =>
              startPractice.mutate({
                scope_type: "CONCEPT",
                scope_id: conceptId,
                question_count: Math.min(questions.length, 10),
              })
            }
          >
            {startPractice.isPending ? "Starting practice…" : "Start concept practice"}
          </Button>
          {startPractice.isError && (
            <p className="text-xs text-destructive">{practiceStartMessage(startPractice.error)}</p>
          )}
        </div>
      )}

      {questions.map((item) => {
        const body = item.latest_version?.body as unknown as QuestionBody | undefined;
        if (!body?.stem || !body.options?.length) return null;
        return <ConceptPracticeQuestion key={item.id} id={item.id} body={body} />;
      })}

      {notes.length === 0 && questions.length === 0 && flashcards.length === 0 && (
        <EmptyState
          icon={BookOpen}
          title="No published content yet"
          description="Notes, questions, and flashcards will appear here after editorial publish."
        />
      )}

      <AiTutorBox conceptId={conceptId} />
    </StudentPage>
  );
}
