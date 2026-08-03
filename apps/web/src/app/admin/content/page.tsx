"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConceptPicker } from "@/components/concept-picker";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api-client";
import { aiApi } from "@/features/ai/api";
import { cmsApi, type WorkflowState } from "@/features/cms/api";

const STATE_VARIANT: Record<WorkflowState, "default" | "secondary" | "outline" | "destructive"> = {
  DRAFT: "outline",
  IN_REVIEW: "secondary",
  CHANGES_REQUESTED: "destructive",
  APPROVED: "secondary",
  PUBLISHED: "default",
  ARCHIVED: "outline",
};

const PAGE_SIZE = 20;

function QuestionsTab() {
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [genConceptId, setGenConceptId] = useState<string | null>(null);
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["cms", "list", statusFilter, search, page],
    queryFn: () => cmsApi.list({ status: statusFilter || undefined, search: search || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  });

  const generate = useMutation({
    mutationFn: () => aiApi.generateQuestion({ concept_id: genConceptId! }),
    onSuccess: (item) => router.push(`/admin/content/${item.id}`),
  });

  const bulkAction = useMutation({
    mutationFn: (action: "publish" | "archive") => cmsApi.bulkAction(Array.from(selected), action),
    onSuccess: () => {
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: ["cms", "list"] });
    },
  });

  const items = data?.data ?? [];
  const total = data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Generate with AI</CardTitle>
          <CardDescription>Pick a concept and let the Question Generator agent draft a question for review.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {generate.isError && (
            <Alert variant="destructive">
              <AlertDescription>{generate.error instanceof ApiError ? generate.error.message : "Something went wrong"}</AlertDescription>
            </Alert>
          )}
          <ConceptPicker value={genConceptId} onChange={setGenConceptId} />
          <Button className="w-fit" disabled={!genConceptId || generate.isPending} onClick={() => generate.mutate()}>
            {generate.isPending ? "Generating…" : "Generate question"}
          </Button>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All statuses</option>
          {Object.keys(STATE_VARIANT).map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <Input
          placeholder="Search by title…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          className="w-56"
        />
        {selected.size > 0 && (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{selected.size} selected</span>
            <Button size="sm" variant="outline" disabled={bulkAction.isPending} onClick={() => bulkAction.mutate("publish")}>
              Bulk publish
            </Button>
            <Button size="sm" variant="outline" disabled={bulkAction.isPending} onClick={() => bulkAction.mutate("archive")}>
              Bulk archive
            </Button>
          </div>
        )}
      </div>

      {bulkAction.data && (
        <Alert>
          <AlertDescription>
            {bulkAction.data.filter((r) => r.success).length} succeeded, {bulkAction.data.filter((r) => !r.success).length} failed.
          </AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-live="polite">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3">
          {items.map((item) => (
            <Card key={item.id} className="transition-colors hover:bg-muted/50">
              <CardHeader className="flex-row items-center gap-3 space-y-0">
                <input
                  type="checkbox"
                  aria-label={`Select ${item.title}`}
                  checked={selected.has(item.id)}
                  onChange={() => toggleSelected(item.id)}
                  onClick={(e) => e.stopPropagation()}
                  className="size-4"
                />
                <Link href={`/admin/content/${item.id}`} className="flex flex-1 items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-base">{item.title}</CardTitle>
                    <p className="text-sm text-muted-foreground">
                      {item.content_type} · {item.language}
                    </p>
                  </div>
                  <Badge variant={STATE_VARIANT[item.status]}>{item.status}</Badge>
                </Link>
              </CardHeader>
            </Card>
          ))}
          {items.length === 0 && <EmptyState title="No content matches these filters" />}
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
  );
}

function ReportsTab() {
  const [statusFilter, setStatusFilter] = useState("OPEN");
  const [page, setPage] = useState(0);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["cms", "reports", statusFilter, page],
    queryFn: () => cmsApi.listReports({ status: statusFilter || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  });

  const resolve = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "RESOLVED" | "DISMISSED" }) => cmsApi.resolveReport(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cms", "reports"] }),
  });

  const reports = data?.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <select
        className="h-9 w-fit rounded-md border bg-background px-2 text-sm"
        value={statusFilter}
        onChange={(e) => {
          setStatusFilter(e.target.value);
          setPage(0);
        }}
      >
        <option value="OPEN">Open</option>
        <option value="RESOLVED">Resolved</option>
        <option value="DISMISSED">Dismissed</option>
        <option value="">All</option>
      </select>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : reports.length === 0 ? (
        <EmptyState title="No reports here" description="Student-submitted content reports will show up in this queue." />
      ) : (
        <div className="grid gap-3">
          {reports.map((report) => (
            <Card key={report.id}>
              <CardContent className="flex flex-col gap-2 pt-6 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <Badge variant="outline">{report.reason}</Badge>
                  <span className="text-xs text-muted-foreground">{new Date(report.created_at).toLocaleString()}</span>
                </div>
                {report.comment && <p className="text-muted-foreground">{report.comment}</p>}
                <Link href={`/admin/content/${report.content_item_id}`} className="text-xs underline underline-offset-2">
                  View question
                </Link>
                {report.status === "OPEN" && (
                  <div className="flex gap-2 pt-1">
                    <Button size="sm" variant="outline" onClick={() => resolve.mutate({ id: report.id, status: "RESOLVED" })}>
                      Mark resolved
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => resolve.mutate({ id: report.id, status: "DISMISSED" })}>
                      Dismiss
                    </Button>
                  </div>
                )}
                {report.status !== "OPEN" && <Badge variant="secondary">{report.status}</Badge>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ContentListPage() {
  const searchParams = useSearchParams();
  const defaultTab = searchParams.get("tab") === "reports" ? "reports" : "questions";

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-4xl flex-col gap-6">
        <div className="flex items-center justify-between">
          <h1 className="font-heading text-xl font-semibold">Content</h1>
          <Link href="/admin/content/new" className={cn(buttonVariants())}>
            New content
          </Link>
        </div>

        <Tabs defaultValue={defaultTab}>
          <TabsList>
            <TabsTrigger value="questions">Questions & Content</TabsTrigger>
            <TabsTrigger value="reports">Reports</TabsTrigger>
          </TabsList>
          <TabsContent value="questions" className="mt-4">
            <QuestionsTab />
          </TabsContent>
          <TabsContent value="reports" className="mt-4">
            <ReportsTab />
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
