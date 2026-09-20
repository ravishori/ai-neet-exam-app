"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";
import { cmsApi, type RiskBucket } from "@/features/cms/api";
import { academicApi } from "@/features/academic/api";

const RISK_VARIANT: Record<RiskBucket, "default" | "secondary" | "destructive"> = {
  RED: "destructive",
  AMBER: "secondary",
  GREEN: "default",
};

const PAGE_SIZE = 25;

export default function ReviewQueuePage() {
  const router = useRouter();
  const [subjectId, setSubjectId] = useState("");
  const [classLevel, setClassLevel] = useState("");
  const [chapterId, setChapterId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [riskBucket, setRiskBucket] = useState<RiskBucket | "">("");
  const [offset, setOffset] = useState(0);
  const [sessionSize, setSessionSize] = useState(25);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const subjectsQuery = useQuery({
    queryKey: ["academic", "subjects"],
    queryFn: () => academicApi.subjects(),
  });
  const chaptersQuery = useQuery({
    queryKey: ["academic", "chapters", subjectId],
    queryFn: () => academicApi.chapters(subjectId),
    enabled: Boolean(subjectId),
  });
  const topicsQuery = useQuery({
    queryKey: ["academic", "topics", chapterId],
    queryFn: () => academicApi.topics(chapterId),
    enabled: Boolean(chapterId),
  });

  const filters = useMemo(
    () => ({
      subject_id: subjectId || undefined,
      class_level: classLevel || undefined,
      chapter_id: chapterId || undefined,
      topic_id: topicId || undefined,
      batch_id: batchId || undefined,
      risk_bucket: (riskBucket || undefined) as RiskBucket | undefined,
    }),
    [subjectId, classLevel, chapterId, topicId, batchId, riskBucket],
  );

  const queueQuery = useQuery({
    queryKey: ["cms", "review-queue", filters, offset],
    queryFn: () => cmsApi.reviewQueue({ ...filters, limit: PAGE_SIZE, offset }),
  });

  const rows = queueQuery.data?.data ?? [];
  const meta = queueQuery.data?.meta;
  const total = meta?.total ?? 0;
  const trustedOnPage = rows.filter((r) => r.is_trusted_factory).length;

  const startSessionMutation = useMutation({
    mutationFn: () =>
      cmsApi.createReviewSession({
        session_size: sessionSize,
        ...filters,
      }),
    onSuccess: (session) => {
      setSessionError(null);
      router.push(`/admin/content/review-queue/session/${session.id}`);
    },
    onError: (err) => {
      setSessionError(err instanceof ApiError ? err.message : "Failed to start review session");
    },
  });

  function resetFiltersDownstream(scope: "subject" | "chapter") {
    if (scope === "subject") {
      setChapterId("");
      setTopicId("");
    } else {
      setTopicId("");
    }
    setOffset(0);
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Review Queue</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          IN_REVIEW questions awaiting human decision. Never auto-approved or auto-published.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Filters</CardTitle>
          <CardDescription>Deterministic risk bucketing — no AI/LLM scoring.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <select
              aria-label="Subject"
              data-testid="review-queue-subject-filter"
              className="h-9 w-full min-w-0 rounded-md border bg-background px-2 text-sm"
              value={subjectId}
              onChange={(e) => {
                setSubjectId(e.target.value);
                resetFiltersDownstream("subject");
              }}
            >
              <option value="">All subjects</option>
              {(subjectsQuery.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>

            <select
              aria-label="Class"
              data-testid="review-queue-class-filter"
              className="h-9 w-full min-w-0 rounded-md border bg-background px-2 text-sm"
              value={classLevel}
              onChange={(e) => {
                setClassLevel(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All classes</option>
              <option value="11">Class 11</option>
              <option value="12">Class 12</option>
            </select>

            <select
              aria-label="Chapter"
              data-testid="review-queue-chapter-filter"
              className="h-9 w-full min-w-0 rounded-md border bg-background px-2 text-sm"
              value={chapterId}
              disabled={!subjectId}
              onChange={(e) => {
                setChapterId(e.target.value);
                resetFiltersDownstream("chapter");
              }}
            >
              <option value="">All chapters</option>
              {(chaptersQuery.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>

            <select
              aria-label="Topic"
              data-testid="review-queue-topic-filter"
              className="h-9 w-full min-w-0 rounded-md border bg-background px-2 text-sm"
              value={topicId}
              disabled={!chapterId}
              onChange={(e) => {
                setTopicId(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All topics</option>
              {(topicsQuery.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>

            <Input
              aria-label="Batch ID"
              data-testid="review-queue-batch-filter"
              placeholder="Batch ID"
              className="h-9 w-full min-w-0"
              value={batchId}
              onChange={(e) => {
                setBatchId(e.target.value);
                setOffset(0);
              }}
            />

            <select
              aria-label="Risk bucket"
              data-testid="review-queue-risk-filter"
              className="h-9 w-full min-w-0 rounded-md border bg-background px-2 text-sm"
              value={riskBucket}
              onChange={(e) => {
                setRiskBucket(e.target.value as RiskBucket | "");
                setOffset(0);
              }}
            >
              <option value="">All risk buckets</option>
              <option value="RED">RED</option>
              <option value="AMBER">AMBER</option>
              <option value="GREEN">GREEN</option>
            </select>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge variant="outline" data-testid="review-queue-total">
              Total {total}
            </Badge>
            <Badge variant="secondary" data-testid="review-queue-trusted-count">
              Trusted Factory (this page) {trustedOnPage}/{rows.length}
            </Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-3 pb-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle className="text-base">Start a review session</CardTitle>
            <CardDescription>Default 25 questions, uses current filters.</CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-sm" htmlFor="session-size">
              Size
              <Input
                id="session-size"
                type="number"
                min={1}
                max={200}
                className="h-9 w-20"
                value={sessionSize}
                onChange={(e) => setSessionSize(Number(e.target.value) || 25)}
              />
            </label>
            <Button
              type="button"
              data-testid="start-review-session"
              disabled={startSessionMutation.isPending}
              onClick={() => startSessionMutation.mutate()}
            >
              Start Review Session
            </Button>
          </div>
        </CardHeader>
        {sessionError ? (
          <CardContent className="pt-0">
            <Alert variant="destructive">
              <AlertDescription>{sessionError}</AlertDescription>
            </Alert>
          </CardContent>
        ) : null}
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Queue</CardTitle>
          <CardDescription>Ordered by created_at, id (stable).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {queueQuery.isLoading ? (
            <Skeleton className="h-40 w-full" data-testid="review-queue-loading" />
          ) : queueQuery.isError ? (
            <Alert variant="destructive" data-testid="review-queue-error">
              <AlertDescription>
                {queueQuery.error instanceof ApiError ? queueQuery.error.message : "Queue failed to load"}
              </AlertDescription>
            </Alert>
          ) : rows.length === 0 ? (
            <EmptyState icon={ClipboardList} title="Nothing in this queue" description="Clear filters or check back later." />
          ) : (
            <ul className="divide-y rounded-md border" data-testid="review-queue-list">
              {rows.map((row) => (
                <li key={row.id} className="flex flex-col gap-1 px-3 py-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={RISK_VARIANT[row.risk_bucket]}>{row.risk_bucket}</Badge>
                    {row.is_trusted_factory ? <Badge variant="outline">Trusted Factory</Badge> : null}
                    {row.academic.class_level ? <Badge variant="outline">Class {row.academic.class_level}</Badge> : null}
                  </div>
                  <p className="font-medium">{row.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {row.academic.subject?.name ?? "—"} · {row.academic.chapter?.name ?? "—"} ·{" "}
                    {row.academic.topic?.name ?? "—"}
                  </p>
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-center justify-between pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            >
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              {total === 0 ? "0" : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset((o) => o + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
