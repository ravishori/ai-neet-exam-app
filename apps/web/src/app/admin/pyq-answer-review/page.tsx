"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";
import { pyqAnswerReviewApi } from "@/features/pyq-answer-review/api";

const PAGE_SIZE = 25;

export default function PyqAnswerReviewQueuePage() {
  const router = useRouter();
  const [examYear, setExamYear] = useState("");
  const [subject, setSubject] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const countsQuery = useQuery({
    queryKey: ["pyq-answer-review", "counts"],
    queryFn: () => pyqAnswerReviewApi.counts(),
  });

  const queueQuery = useQuery({
    queryKey: ["pyq-answer-review", "list", examYear, subject, search, page],
    queryFn: () =>
      pyqAnswerReviewApi.list({
        exam_year: examYear || undefined,
        subject: subject || undefined,
        search: search || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  const counts = countsQuery.data;
  const rows = queueQuery.data?.items ?? [];

  function resetAndSet(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">PYQ Answer Review</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Individual human review of NEET_PYQ_OFFICIAL questions with four complete, distinct options.
          Never auto-resolved by AI.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Progress</CardTitle>
          <CardDescription>Live counts, recomputed from current database state.</CardDescription>
        </CardHeader>
        <CardContent>
          {countsQuery.isLoading ? (
            <Skeleton className="h-8 w-full" data-testid="counts-loading" />
          ) : countsQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription>
                {countsQuery.error instanceof ApiError ? countsQuery.error.message : "Counts failed to load"}
              </AlertDescription>
            </Alert>
          ) : counts ? (
            <div className="flex flex-wrap items-center gap-2 text-sm" data-testid="counts-summary">
              <Badge variant="outline">Eligible {counts.eligible}</Badge>
              <Badge variant="secondary">Reviewed {counts.reviewed_by_human}</Badge>
              <Badge variant="outline">Skipped {counts.skipped}</Badge>
              <Badge variant="outline">Needs manual review {counts.requires_manual_review}</Badge>
              <Badge variant="outline">Structurally invalid {counts.structurally_invalid}</Badge>
              <Badge variant="outline">Total pending {counts.total_pending}</Badge>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <Input
              aria-label="Exam year"
              placeholder="Exam year (e.g. 2024)"
              value={examYear}
              onChange={(e) => resetAndSet(setExamYear, e.target.value)}
            />
            <Input
              aria-label="Subject"
              placeholder="Subject (e.g. Physics)"
              value={subject}
              onChange={(e) => resetAndSet(setSubject, e.target.value)}
            />
            <Input
              aria-label="Search"
              placeholder="Search staging ID or stem text"
              value={search}
              onChange={(e) => resetAndSet(setSearch, e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Eligible queue</CardTitle>
          <CardDescription>Ordered by exam year, question number.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {queueQuery.isLoading ? (
            <Skeleton className="h-40 w-full" data-testid="queue-loading" />
          ) : queueQuery.isError ? (
            <Alert variant="destructive" data-testid="queue-error">
              <AlertDescription>
                {queueQuery.error instanceof ApiError ? queueQuery.error.message : "Queue failed to load"}
              </AlertDescription>
            </Alert>
          ) : rows.length === 0 ? (
            <EmptyState icon={ClipboardList} title="Nothing in this queue" description="Clear filters or check back later." />
          ) : (
            <ul className="divide-y rounded-md border" data-testid="queue-list">
              {rows.map((row) => (
                <li
                  key={row.id}
                  className="flex cursor-pointer flex-col gap-1 px-3 py-3 text-sm hover:bg-muted/50"
                  onClick={() => router.push(`/admin/pyq-answer-review/${row.id}`)}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    {row.exam_year ? <Badge variant="outline">{row.exam_year}</Badge> : null}
                    {row.subject ? <Badge variant="outline">{row.subject}</Badge> : null}
                    <span className="text-xs text-muted-foreground">{row.staging_id}</span>
                  </div>
                  <p className="font-medium">{row.stem_preview}</p>
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-center justify-between pt-2">
            <Button type="button" variant="outline" size="sm" disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">Page {page}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={rows.length < PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
