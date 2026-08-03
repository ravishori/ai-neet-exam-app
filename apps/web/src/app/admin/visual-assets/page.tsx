"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { visualAssetsApi, type ReviewStatus } from "@/features/visual-assets/api";

const STATUS_VARIANT: Record<ReviewStatus, "default" | "secondary" | "destructive" | "outline"> = {
  AUTO_DETECTED: "secondary",
  VERIFIED: "default",
  NEEDS_MANUAL_BBOX: "outline",
  REJECTED: "destructive",
};

const PAGE_SIZE = 12;

function RejectDialog({ onReject, isPending }: { onReject: (reason: string) => void; isPending: boolean }) {
  const [reason, setReason] = useState("");
  return (
    <Dialog>
      <DialogTrigger render={<Button type="button" size="sm" variant="destructive" />}>Reject</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reject visual asset</DialogTitle>
          <DialogDescription>Explain why this detected asset shouldn&apos;t be used.</DialogDescription>
        </DialogHeader>
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Cropped incorrectly, unreadable, not a real diagram…" rows={3} />
        <DialogFooter>
          <Button type="button" variant="destructive" disabled={!reason.trim() || isPending} onClick={() => onReject(reason)}>
            {isPending ? "Rejecting…" : "Reject"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function VisualAssetsPage() {
  const [statusFilter, setStatusFilter] = useState<ReviewStatus | "">("AUTO_DETECTED");
  const [page, setPage] = useState(0);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["visual-assets", statusFilter, page],
    queryFn: () => visualAssetsApi.list({ reviewStatus: statusFilter || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  });

  const approve = useMutation({
    mutationFn: (id: string) => visualAssetsApi.approve(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["visual-assets"] }),
  });
  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => visualAssetsApi.reject(id, reason),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["visual-assets"] }),
  });

  const assets = data?.data ?? [];
  const total = data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div>
          <h1 className="font-heading text-xl font-semibold">Visual Asset Review</h1>
          <p className="text-sm text-muted-foreground">Approve or reject diagrams, tables, and equations detected from ingested PDFs.</p>
        </div>

        <select
          className="h-9 w-fit rounded-md border bg-background px-2 text-sm"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as ReviewStatus | "");
            setPage(0);
          }}
        >
          <option value="AUTO_DETECTED">Needs review</option>
          <option value="NEEDS_MANUAL_BBOX">Needs manual bounding box</option>
          <option value="VERIFIED">Verified</option>
          <option value="REJECTED">Rejected</option>
          <option value="">All</option>
        </select>

        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-live="polite">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-64 w-full" />
            ))}
          </div>
        ) : assets.length === 0 ? (
          <EmptyState title="Nothing here" description="No visual assets match this filter." />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {assets.map((asset) => (
              <Card key={asset.id} className="overflow-hidden">
                <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
                  <Badge variant={STATUS_VARIANT[asset.review_status]}>{asset.review_status}</Badge>
                  <span className="text-xs text-muted-foreground">page {asset.source_page}</span>
                </CardHeader>
                <CardContent className="flex flex-col gap-2">
                  {asset.has_image ? (
                    <img
                      src={`/api/admin/visual-assets/${asset.id}`}
                      alt={asset.vision_description ?? `${asset.asset_type} detected on page ${asset.source_page}`}
                      className="h-40 w-full rounded-md border border-border object-contain"
                    />
                  ) : (
                    <div className="flex h-40 w-full items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">
                      No image file
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {asset.asset_type} · {asset.detection_method}
                  </p>
                  {asset.rejection_reason && <p className="text-xs text-destructive">{asset.rejection_reason}</p>}
                </CardContent>
                {(asset.review_status === "AUTO_DETECTED" || asset.review_status === "NEEDS_MANUAL_BBOX") && (
                  <CardFooter className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      disabled={approve.isPending}
                      onClick={() => approve.mutate(asset.id)}
                    >
                      Approve
                    </Button>
                    <RejectDialog isPending={reject.isPending} onReject={(reason) => reject.mutate({ id: asset.id, reason })} />
                  </CardFooter>
                )}
              </Card>
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
