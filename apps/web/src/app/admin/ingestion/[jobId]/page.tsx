"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ingestionApi } from "@/features/ingestion/api";
import { ApiError } from "@/lib/api-client";

export default function IngestionJobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const query = useQuery({
    queryKey: ["ingestion", "job-detail", jobId],
    queryFn: () => ingestionApi.jobDetail(jobId),
    retry: (failureCount, error) => (error instanceof ApiError && error.status === 404 ? false : failureCount < 2),
  });

  const notFound = query.isError && query.error instanceof ApiError && query.error.status === 404;

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
          <Link href="/admin/ingestion" className="underline-offset-4 hover:underline">
            &larr; Back to PDF Management
          </Link>
        </nav>

        {query.isLoading && <Skeleton className="h-64 w-full" aria-busy="true" aria-live="polite" />}
        {notFound && <EmptyState title="Ingestion job not found" />}

        {query.data && (
          <>
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="text-lg">{query.data.original_filename ?? query.data.source_file_path}</CardTitle>
                  <Badge>{query.data.status}</Badge>
                </div>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <div>
                  <div className="text-muted-foreground">Sections</div>
                  <div className="text-lg font-semibold tabular-nums">{query.data.sections_detected}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Questions</div>
                  <div className="text-lg font-semibold tabular-nums">{query.data.questions_generated}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Knowledge Units</div>
                  <div className="text-lg font-semibold tabular-nums">{query.data.knowledge_units_created}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Visual Assets</div>
                  <div className="text-lg font-semibold tabular-nums">{query.data.visual_assets_detected}</div>
                </div>
                {query.data.error_message && (
                  <div className="col-span-2 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-destructive sm:col-span-4">
                    {query.data.error_message}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Sections ({query.data.sections.length})</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {query.data.sections.length === 0 && <p className="text-sm text-muted-foreground">No sections extracted yet.</p>}
                {query.data.sections.map((s) => (
                  <div key={s.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
                    <span>{s.heading ?? "Untitled"}</span>
                    <span className="text-xs text-muted-foreground">page {s.source_page ?? "—"}</span>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Knowledge Units ({query.data.knowledge_units.length})</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {query.data.knowledge_units.length === 0 && <p className="text-sm text-muted-foreground">None produced yet.</p>}
                {query.data.knowledge_units.map((u) => (
                  <Link
                    key={u.id}
                    href={`/admin/knowledge-units/${u.id}`}
                    className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm hover:bg-muted/50"
                  >
                    <span className="truncate">{u.summary}</span>
                    <Badge variant={u.validation_status === "PASSED" ? "default" : u.validation_status === "FAILED" ? "destructive" : "secondary"}>
                      {u.validation_status}
                    </Badge>
                  </Link>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Visual Assets ({query.data.visual_assets.length})</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2">
                {query.data.visual_assets.length === 0 && <p className="text-sm text-muted-foreground">None detected yet.</p>}
                {query.data.visual_assets.map((a) => (
                  <div key={a.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
                    <span>
                      {a.asset_type} · page {a.source_page ?? "—"}
                    </span>
                    <Badge variant="outline">{a.review_status}</Badge>
                  </div>
                ))}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </main>
  );
}
