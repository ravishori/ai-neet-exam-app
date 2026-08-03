"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { FlipCard } from "@/components/flip-card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
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
    <main className="flex flex-1 flex-col gap-6 px-4 py-8 sm:px-6 sm:py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Flashcards</h1>
        <p className="text-sm text-muted-foreground">Tap a card to flip it. Quick revision by subject, chapter, topic, or concept.</p>
      </div>

      <Card>
        <CardContent className="grid grid-cols-2 gap-4 pt-6 sm:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <Label>Subject</Label>
            <select
              className="h-9 rounded-md border bg-background px-2 text-sm"
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
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Chapter</Label>
            <select
              className="h-9 rounded-md border bg-background px-2 text-sm disabled:opacity-50"
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
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Topic</Label>
            <select
              className="h-9 rounded-md border bg-background px-2 text-sm disabled:opacity-50"
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
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Concept</Label>
            <select
              className="h-9 rounded-md border bg-background px-2 text-sm disabled:opacity-50"
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
            </select>
          </div>
        </CardContent>
      </Card>

      {flashcardsQuery.isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
          {flashcardsQuery.data.data.map((card) => (
            <FlipCard
              key={card.id}
              front={card.front ?? ""}
              back={card.back ?? ""}
              imageUrl={card.image_url}
              tags={[card.subject, card.chapter, card.concept].filter((t): t is { id: string; name: string } => !!t).map((t) => ({ label: t.name }))}
            />
          ))}
        </div>
      )}

      {total > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {showingFrom}-{showingTo} of {total}
          </p>
          <div className="flex gap-2">
            <Button variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              Previous
            </Button>
            <Button variant="outline" disabled={showingTo >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
              Next
            </Button>
          </div>
        </div>
      )}
    </main>
  );
}
