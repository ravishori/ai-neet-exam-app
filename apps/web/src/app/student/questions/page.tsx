"use client";

import { ImageIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { academicApi } from "@/features/academic/api";
import { questionsApi, type QuestionSummary, type ScopeType } from "@/features/questions/api";
import { searchApi, type SearchResultItem } from "@/features/search/api";

const PAGE_SIZE = 20;

function QuestionOptions({ options }: { options: { label: string; text: string }[] }) {
  return (
    <ul className="grid grid-cols-1 gap-1.5 text-sm text-muted-foreground sm:grid-cols-2">
      {options.map((opt) => (
        <li key={opt.label}>
          <span className="font-medium text-foreground">{opt.label}.</span> {opt.text}
        </li>
      ))}
    </ul>
  );
}

function QuestionTags({ q }: { q: QuestionSummary | SearchResultItem }) {
  const imageCount = "images" in q ? q.images.length : 0;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
      {q.subject && <Badge variant="outline">{q.subject.name}</Badge>}
      {q.chapter && <Badge variant="outline">{q.chapter.name}</Badge>}
      {q.concept && <Badge variant="outline">{q.concept.name}</Badge>}
      {q.pyq_year && <Badge variant="ghost">PYQ {q.pyq_year}</Badge>}
      {imageCount > 0 && (
        <Badge variant="ghost" className="gap-1">
          <ImageIcon className="size-3" aria-hidden="true" />
          {imageCount > 1 ? `${imageCount} images` : "Diagram"}
        </Badge>
      )}
    </div>
  );
}

function DifficultyBadge({ difficulty }: { difficulty: string | null }) {
  if (!difficulty) return null;
  return (
    <Badge variant={difficulty === "hard" ? "destructive" : difficulty === "easy" ? "secondary" : "outline"}>{difficulty}</Badge>
  );
}

const MATCHED_FIELD_LABEL: Record<string, string> = {
  stem: "question",
  options: "options",
  explanation: "explanation",
  concept: "concept",
  topic: "topic",
  chapter: "chapter",
  subject: "subject",
  knowledge_unit: "knowledge unit",
};

export default function QuestionBrowserPage() {
  const [keyword, setKeyword] = useState("");
  const [submittedKeyword, setSubmittedKeyword] = useState("");
  const [subjectId, setSubjectId] = useState<string | null>(null);
  const [chapterId, setChapterId] = useState<string | null>(null);
  const [topicId, setTopicId] = useState<string | null>(null);
  const [conceptId, setConceptId] = useState<string | null>(null);
  const [difficulty, setDifficulty] = useState<string>("");
  const [pyqYear, setPyqYear] = useState<string>("");
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

  // Most-specific filter wins — selecting a concept already implies its topic/chapter/subject.
  const scope: { scopeType: ScopeType; scopeId: string } | Record<string, never> = conceptId
    ? { scopeType: "CONCEPT", scopeId: conceptId }
    : topicId
      ? { scopeType: "TOPIC", scopeId: topicId }
      : chapterId
        ? { scopeType: "CHAPTER", scopeId: chapterId }
        : subjectId
          ? { scopeType: "SUBJECT", scopeId: subjectId }
          : {};

  const isSearching = submittedKeyword.trim().length > 0;

  const browseQuery = useQuery({
    queryKey: ["questions", scope, offset],
    queryFn: () => questionsApi.list({ ...scope, limit: PAGE_SIZE, offset }),
    enabled: !isSearching,
  });

  const searchQuery = useQuery({
    queryKey: ["search", submittedKeyword, scope, difficulty, pyqYear, offset],
    queryFn: () =>
      searchApi.search({
        q: submittedKeyword,
        ...scope,
        difficulty: difficulty || undefined,
        pyqYear: pyqYear ? Number(pyqYear) : undefined,
        limit: PAGE_SIZE,
        offset,
      }),
    enabled: isSearching,
  });

  const activeQuery = isSearching ? searchQuery : browseQuery;
  const results = activeQuery.data?.data ?? [];
  const total = activeQuery.data?.meta.total ?? 0;
  const searchMode = isSearching ? (searchQuery.data?.meta.search_mode ?? null) : null;

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

  const onSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittedKeyword(keyword);
    setOffset(0);
  };

  const clearSearch = () => {
    setKeyword("");
    setSubmittedKeyword("");
    setOffset(0);
  };

  const showingFrom = total === 0 ? 0 : offset + 1;
  const showingTo = Math.min(offset + PAGE_SIZE, total);

  return (
    <main className="flex flex-1 flex-col gap-6 px-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Questions</h1>
        <p className="text-sm text-muted-foreground">Search or browse the published question bank.</p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 pt-6">
          <form onSubmit={onSearchSubmit} className="flex gap-2">
            <Input
              placeholder="Search question text, options, explanation, chapter, topic…"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="flex-1"
            />
            <Button type="submit">Search</Button>
            {isSearching && (
              <Button type="button" variant="outline" onClick={clearSearch}>
                Clear
              </Button>
            )}
          </form>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-6">
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

            <div className="flex flex-col gap-1.5">
              <Label>Difficulty {!isSearching && <span className="text-muted-foreground">(search only)</span>}</Label>
              <select
                className="h-9 rounded-md border bg-background px-2 text-sm disabled:opacity-50"
                value={difficulty}
                disabled={!isSearching}
                onChange={(e) => {
                  setDifficulty(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">Any</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label>PYQ year {!isSearching && <span className="text-muted-foreground">(search only)</span>}</Label>
              <Input
                type="number"
                placeholder="e.g. 2023"
                value={pyqYear}
                disabled={!isSearching}
                onChange={(e) => {
                  setPyqYear(e.target.value);
                  setOffset(0);
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {isSearching && searchMode === "fuzzy" && (
        <p className="text-sm text-muted-foreground">
          No exact match for &ldquo;{submittedKeyword}&rdquo; — showing close (typo-tolerant) matches instead.
        </p>
      )}

      {activeQuery.isLoading ? (
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : results.length === 0 ? (
        <EmptyState
          title={isSearching ? `No questions match "${submittedKeyword}"` : "No published questions here yet"}
          description={
            isSearching
              ? "Try a different keyword or a broader filter."
              : "Try a broader filter, or check back once more content has been ingested and published."
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          {results.map((q) => (
            <Link
              key={q.id}
              href={`/student/questions/${q.id}`}
              aria-label={`View question: ${q.stem ?? "untitled question"}`}
              className="rounded-xl transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-3">
                    <CardTitle className="text-base font-normal leading-snug">
                      {isSearching && "snippet" in q ? (
                        <>
                          {(q as SearchResultItem).snippet.map((seg, i) =>
                            seg.highlighted ? (
                              <mark key={i} className="rounded bg-primary/20 px-0.5 text-foreground">
                                {seg.text}
                              </mark>
                            ) : (
                              <span key={i}>{seg.text}</span>
                            )
                          )}
                        </>
                      ) : (
                        q.stem
                      )}
                    </CardTitle>
                    <DifficultyBadge difficulty={q.difficulty} />
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-3 pt-0">
                  <QuestionOptions options={q.options} />
                  <QuestionTags q={q} />
                  {isSearching && "matched_fields" in q && (q as SearchResultItem).matched_fields.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Matched in: {(q as SearchResultItem).matched_fields.map((f) => MATCHED_FIELD_LABEL[f] ?? f).join(", ")}
                    </p>
                  )}
                </CardContent>
              </Card>
            </Link>
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
