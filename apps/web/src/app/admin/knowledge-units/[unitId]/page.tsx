"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { knowledgeApi, type ValidationStatus } from "@/features/knowledge/api";
import { ApiError } from "@/lib/api-client";

const STATUS_VARIANT: Record<ValidationStatus, "default" | "secondary" | "destructive"> = {
  PENDING: "secondary",
  PASSED: "default",
  FAILED: "destructive",
};

export default function KnowledgeUnitDetailPage() {
  const { unitId } = useParams<{ unitId: string }>();
  const query = useQuery({
    queryKey: ["knowledge-unit", unitId],
    queryFn: () => knowledgeApi.get(unitId),
    retry: (failureCount, error) => (error instanceof ApiError && error.status === 404 ? false : failureCount < 2),
  });

  const notFound = query.isError && query.error instanceof ApiError && query.error.status === 404;

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
          <Link href="/admin/knowledge-units" className="underline-offset-4 hover:underline">
            &larr; Back to Knowledge Units
          </Link>
        </nav>

        {query.isLoading && <Skeleton className="h-64 w-full" aria-busy="true" aria-live="polite" />}
        {notFound && <EmptyState title="Knowledge unit not found" />}

        {query.data && (
          <>
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-lg">{query.data.concept_name ?? "Unknown concept"}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      Version {query.data.version} · Confidence {(query.data.extraction_confidence * 100).toFixed(0)}%
                    </p>
                  </div>
                  <Badge variant={STATUS_VARIANT[query.data.validation_status]}>{query.data.validation_status}</Badge>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <p className="text-sm">{query.data.summary}</p>

                {query.data.validation_detail && (
                  <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                    {query.data.validation_detail}
                  </div>
                )}

                <div>
                  <h2 className="mb-2 text-sm font-medium text-foreground">Structured facts</h2>
                  <ul className="flex flex-col gap-1.5 text-sm text-muted-foreground">
                    {query.data.structured_facts.map((fact, idx) => (
                      <li key={idx} className="rounded-md border border-border px-3 py-2">
                        {String(fact)}
                      </li>
                    ))}
                  </ul>
                </div>

                {query.data.source_section && (
                  <p className="text-xs text-muted-foreground">
                    Source: {query.data.source_section.heading ?? "Untitled section"}
                    {query.data.source_section.source_page && ` (page ${query.data.source_section.source_page})`}
                  </p>
                )}

                {query.data.visual_assets.length > 0 && (
                  <div>
                    <h2 className="mb-2 text-sm font-medium text-foreground">Linked visual assets</h2>
                    <div className="flex flex-wrap gap-1.5">
                      {query.data.visual_assets.map((a) => (
                        <Badge key={a.id} variant="outline">
                          {a.asset_type} · {a.review_status}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {query.data.supersede_chain.length > 0 && (
                  <div>
                    <h2 className="mb-2 text-sm font-medium text-foreground">Supersede chain</h2>
                    <div className="flex flex-col gap-1">
                      {query.data.supersede_chain.map((id) => (
                        <Link key={id} href={`/admin/knowledge-units/${id}`} className="text-xs underline underline-offset-2">
                          {id}
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </main>
  );
}
