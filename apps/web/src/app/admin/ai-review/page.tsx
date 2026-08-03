"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cmsApi } from "@/features/cms/api";

const PAGE_SIZE = 20;

export default function AiReviewQueuePage() {
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["cms", "ai-review-queue", page],
    queryFn: () => cmsApi.aiReviewQueue({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  });

  const items = data?.data ?? [];
  const total = data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <h1 className="font-heading text-xl font-semibold">AI Review Queue</h1>
          <p className="text-sm text-muted-foreground">Content submitted for review, alongside what the AI Evaluator agent flagged.</p>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-2" aria-busy="true" aria-live="polite">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState title="Nothing awaiting review" description="Content submitted for review will show up here with its AI check results." />
        ) : (
          <div className="grid gap-3">
            {items.map((item) => {
              const report = item.latest_version?.ai_check_report;
              return (
                <Link key={item.id} href={`/admin/content/${item.id}`}>
                  <Card className="transition-colors hover:bg-muted/50">
                    <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
                      <div>
                        <CardTitle className="text-base">{item.title}</CardTitle>
                        <p className="text-xs text-muted-foreground">{item.content_type}</p>
                      </div>
                      {report && (
                        <Badge variant={report.status === "completed" ? (report.flags.length > 0 ? "destructive" : "default") : "secondary"}>
                          {report.status === "completed" ? (report.flags.length > 0 ? `${report.flags.length} flag(s)` : "clean") : report.status}
                        </Badge>
                      )}
                    </CardHeader>
                    {report && (
                      <CardContent className="flex flex-col gap-1.5 pt-0 text-sm">
                        {report.reason && <p className="text-muted-foreground">{report.reason}</p>}
                        {report.flags.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {report.flags.map((flag, idx) => (
                              <Badge key={idx} variant="outline" className="text-xs">
                                {flag}
                              </Badge>
                            ))}
                          </div>
                        )}
                        {report.confidence !== null && (
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Sparkles className="size-3" aria-hidden="true" /> Confidence {(report.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </CardContent>
                    )}
                  </Card>
                </Link>
              );
            })}
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
