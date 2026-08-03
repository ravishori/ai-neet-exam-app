"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { knowledgeApi, type ValidationStatus } from "@/features/knowledge/api";

const STATUS_VARIANT: Record<ValidationStatus, "default" | "secondary" | "destructive"> = {
  PENDING: "secondary",
  PASSED: "default",
  FAILED: "destructive",
};

const PAGE_SIZE = 20;

export default function KnowledgeUnitsPage() {
  const [statusFilter, setStatusFilter] = useState<ValidationStatus | "">("");
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["knowledge-units", statusFilter, page],
    queryFn: () =>
      knowledgeApi.list({
        validationStatus: statusFilter || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
  });

  const units = data?.data ?? [];
  const total = data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div>
          <h1 className="font-heading text-xl font-semibold">Knowledge Units</h1>
          <p className="text-sm text-muted-foreground">Structured facts extracted from ingested PDFs, with their validation outcome.</p>
        </div>

        <select
          className="h-9 w-fit rounded-md border bg-background px-2 text-sm"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as ValidationStatus | "");
            setPage(0);
          }}
        >
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="PASSED">Passed</option>
          <option value="FAILED">Failed</option>
        </select>

        {isLoading ? (
          <div className="flex flex-col gap-2" aria-busy="true" aria-live="polite">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : units.length === 0 ? (
          <EmptyState title="No knowledge units match this filter" />
        ) : (
          <div className="grid gap-3">
            {units.map((unit) => (
              <Link key={unit.id} href={`/admin/knowledge-units/${unit.id}`}>
                <Card className="transition-colors hover:bg-muted/50">
                  <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
                    <div>
                      <CardTitle className="text-sm leading-snug">{unit.summary}</CardTitle>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {unit.concept_name ?? "Unknown concept"} · v{unit.version} · confidence {(unit.extraction_confidence * 100).toFixed(0)}%
                      </p>
                    </div>
                    <Badge variant={STATUS_VARIANT[unit.validation_status]}>{unit.validation_status}</Badge>
                  </CardHeader>
                  {unit.superseded_by && (
                    <CardContent className="pt-0 text-xs text-muted-foreground">Superseded by a newer version</CardContent>
                  )}
                </Card>
              </Link>
            ))}
          </div>
        )}

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="size-4" aria-hidden="true" /> Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {page + 1} of {totalPages} · {total} total
            </span>
            <Button variant="outline" size="sm" disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}>
              Next <ChevronRight className="size-4" aria-hidden="true" />
            </Button>
          </div>
        )}
      </div>
    </main>
  );
}
