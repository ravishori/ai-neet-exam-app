"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";
import { cmsApi } from "@/features/cms/api";

export default function ContentDetailPage() {
  const { itemId } = useParams<{ itemId: string }>();
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");

  const { data: item, isLoading, error } = useQuery({
    queryKey: ["cms", "item", itemId],
    queryFn: () => cmsApi.get(itemId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["cms", "item", itemId] });

  const submitMutation = useMutation({ mutationFn: () => cmsApi.submit(itemId), onSuccess: invalidate });
  const approveMutation = useMutation({
    mutationFn: () => cmsApi.review(itemId, { decision: "approve", comment }),
    onSuccess: invalidate,
  });
  const requestChangesMutation = useMutation({
    mutationFn: () => cmsApi.review(itemId, { decision: "request_changes", comment }),
    onSuccess: invalidate,
  });
  const publishMutation = useMutation({ mutationFn: () => cmsApi.publish(itemId), onSuccess: invalidate });
  const archiveMutation = useMutation({ mutationFn: () => cmsApi.archive(itemId), onSuccess: invalidate });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }
  if (error instanceof ApiError && error.status === 404) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Not found.</main>;
  }
  if (!item) return null;

  const anyPending =
    submitMutation.isPending || approveMutation.isPending || requestChangesMutation.isPending ||
    publishMutation.isPending || archiveMutation.isPending;
  const lastError = [submitMutation, approveMutation, requestChangesMutation, publishMutation, archiveMutation]
    .map((m) => m.error)
    .find((e): e is ApiError => e instanceof ApiError);

  return (
    <main className="flex flex-1 justify-center px-6 py-10">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{item.title}</CardTitle>
            <Badge>{item.status}</Badge>
          </div>
          <CardDescription>
            {item.content_type} · v{item.latest_version?.version_no}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {lastError && (
            <Alert variant="destructive">
              <AlertDescription>{lastError.message}</AlertDescription>
            </Alert>
          )}

          <pre className="overflow-x-auto rounded-md border bg-muted p-4 text-xs">
            {JSON.stringify(item.latest_version?.body, null, 2)}
          </pre>

          {item.latest_version?.ai_check_report && (
            <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
              AI check: {JSON.stringify(item.latest_version.ai_check_report.reason)}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            {item.status === "DRAFT" && (
              <Button size="sm" disabled={anyPending} onClick={() => submitMutation.mutate()}>
                Submit for review
              </Button>
            )}

            {item.status === "IN_REVIEW" && (
              <>
                <input
                  className="h-9 flex-1 min-w-40 rounded-md border bg-background px-2 text-sm"
                  placeholder="Review comment (optional)"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
                <Button size="sm" disabled={anyPending} onClick={() => approveMutation.mutate()}>
                  Approve
                </Button>
                <Button size="sm" variant="outline" disabled={anyPending} onClick={() => requestChangesMutation.mutate()}>
                  Request changes
                </Button>
              </>
            )}

            {item.status === "APPROVED" && (
              <Button size="sm" disabled={anyPending} onClick={() => publishMutation.mutate()}>
                Publish
              </Button>
            )}

            {item.status === "PUBLISHED" && (
              <Button size="sm" variant="outline" disabled={anyPending} onClick={() => archiveMutation.mutate()}>
                Archive
              </Button>
            )}

            {item.status === "CHANGES_REQUESTED" && (
              <p className="text-sm text-muted-foreground">
                Changes requested — editing existing drafts isn&apos;t wired into this UI yet; use the API to
                submit a new version.
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
