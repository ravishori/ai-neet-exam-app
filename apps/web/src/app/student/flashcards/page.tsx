"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { FieldSelect } from "@/components/ui/field-select";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { FlipCard } from "@/components/flip-card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardContent,
} from "@/components/ds";
import { academicApi } from "@/features/academic/api";
import { flashcardsApi } from "@/features/flashcards/api";
import type { ScopeType } from "@/features/questions/api";

const PAGE_SIZE = 12;

export default function FlashcardsPage() {
  const [subjectId, setSubjectId] = useState<string | null>(null);
  const [chapterId, setChapterId] = useState<string | null>(null);
  const [topicId, setTopicId] = useState<string | null>(null);
  const [conceptId, setConceptId] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const subjectsQuery = useQuery({ queryKey: ["academic", "subjects"], queryFn: academicApi.subjects });
  const chaptersQuery = useQuery({
    queryKey: ["academic", "chapters", subjectId],
    queryFn: () => academicApi.chapters(subjectId!),
    enabled: !!subjectId,
  });
  const topicsQuery = useQuery({
    queryKey: ["academic", "topics", chapterId],
    queryFn: () => academicApi.topics(chapterId!),
    enabled: !!chapterId,
  });
  const conceptsQuery = useQuery({
    queryKey: ["academic", "concepts", topicId],
    queryFn: () => academicApi.concepts(topicId!),
    enabled: !!topicId,
  });

  const scope: { scopeType: ScopeType; scopeId: string } | Record<string, never> = conceptId
    ? { scopeType: "CONCEPT", scopeId: conceptId }
    : topicId
      ? { scopeType: "TOPIC", scopeId: topicId }
      : chapterId
        ? { scopeType: "CHAPTER", scopeId: chapterId }
        : subjectId
          ? { scopeType: "SUBJECT", scopeId: subjectId }
          : {};

  const flashcardsQuery = useQuery({
    queryKey: ["flashcards", scope, offset],
    queryFn: () => flashcardsApi.list({ ...scope, limit: PAGE_SIZE, offset }),
  });

  const resetBelow = (level: "subject" | "chapter" | "topic") => {
    if (level === "subject") {
      setChapterId(null);
      setTopicId(null);
      setConceptId(null);
    } else if (level === "chapter") {
      setTopicId(null);
      setConceptId(null);
    } else if (level === "topic") {
      setConceptId(null);
    }
    setOffset(0);
  };

  const total = flashcardsQuery.data?.meta.total ?? 0;
  const showingFrom = total === 0 ? 0 : offset + 1;
  const showingTo = Math.min(offset + PAGE_SIZE, total);

  return (
    <StudentPage>
      <PageHeader
        eyebrow="Revision"
        title="Flashcards"
        description='Tap a card to flip it. Filter by subject, chapter, topic, or concept. Cards marked "Needs review" are available for practice but are not scientifically certified.'
      />

      <SurfaceCard accent="none" glass={false}>
        <SurfaceCardContent className="grid grid-cols-2 gap-4 pt-2 sm:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label>Subject</Label>
            <FieldSelect
              className="h-11"
              value={subjectId ?? ""}
              onChange={(e) => {
                setSubjectId(e.target.value || null);
                resetBelow("subject");
              }}
            >
              <option value="">All subjects</option>
              {subjectsQuery.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </FieldSelect>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Chapter</Label>
            <FieldSelect
              className="h-11"
              value={chapterId ?? ""}
              disabled={!subjectId}
              onChange={(e) => {
                setChapterId(e.target.value || null);
                resetBelow("chapter");
              }}
            >
              <option value="">All chapters</option>
              {chaptersQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </FieldSelect>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Topic</Label>
            <FieldSelect
              className="h-11"
              value={topicId ?? ""}
              disabled={!chapterId}
              onChange={(e) => {
                setTopicId(e.target.value || null);
                resetBelow("topic");
              }}
            >
              <option value="">All topics</option>
              {topicsQuery.data?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </FieldSelect>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Concept</Label>
            <FieldSelect
              className="h-11"
              value={conceptId ?? ""}
              disabled={!topicId}
              onChange={(e) => {
                setConceptId(e.target.value || null);
                setOffset(0);
              }}
            >
              <option value="">All concepts</option>
              {conceptsQuery.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </FieldSelect>
          </div>
        </SurfaceCardContent>
      </SurfaceCard>

      {flashcardsQuery.isError ? (
        <Alert variant="destructive" role="alert" data-testid="flashcards-error">
          <AlertTitle>Could not load flashcards</AlertTitle>
          <AlertDescription>
            {flashcardsQuery.error instanceof Error
              ? flashcardsQuery.error.message
              : "Check that you are signed in and the API is reachable, then refresh the page."}
          </AlertDescription>
        </Alert>
      ) : flashcardsQuery.isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      ) : !flashcardsQuery.data || flashcardsQuery.data.data.length === 0 ? (
        <EmptyState
          title="No flashcards here yet"
          description="Try a broader filter, or check back once more content has been ingested and published."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {flashcardsQuery.data.data.map((card) => {
            const cert = card.certification_status;
            const tagLabels = [card.subject, card.chapter, card.concept]
              .filter((t): t is { id: string; name: string } => !!t)
              .map((t) => ({ label: t.name }));
            if (cert === "VERIFIED") {
              tagLabels.push({ label: "Certified" });
            } else if (cert === "REVIEW") {
              tagLabels.push({ label: "Needs review" });
            }
            return (
              <FlipCard
                key={card.id}
                front={card.front ?? ""}
                back={card.back ?? ""}
                imageUrl={card.image_url}
                tags={tagLabels}
              />
            );
          })}
        </div>
      )}

      {total > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {showingFrom}-{showingTo} of {total}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" size="touch" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              Previous
            </Button>
            <Button variant="outline" size="touch" disabled={showingTo >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </StudentPage>
  );
}
