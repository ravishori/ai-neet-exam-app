"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { academicApi } from "@/features/academic/api";
import { ingestionApi, type IngestionJob, type IngestionJobStatus } from "@/features/ingestion/api";
import { ApiError } from "@/lib/api-client";

const JOB_PAGE_SIZE = 20;

const STATUS_VARIANT: Record<IngestionJobStatus, "default" | "secondary" | "destructive" | "outline"> = {
  PENDING: "outline",
  EXTRACTING: "secondary",
  MATCHING: "secondary",
  STRUCTURING: "secondary",
  GENERATING: "secondary",
  COMPLETED: "default",
  FAILED: "destructive",
};

const TERMINAL_STATUSES: IngestionJobStatus[] = ["COMPLETED", "FAILED"];

function JobRow({ job }: { job: IngestionJob }) {
  return (
    <TableRow>
      <TableCell className="font-medium">
        <Link href={`/admin/ingestion/${job.id}`} className="underline-offset-2 hover:underline">
          {job.original_filename ?? job.source_file_path}
        </Link>
      </TableCell>
      <TableCell>
        <Badge variant={STATUS_VARIANT[job.status]}>{job.status}</Badge>
        {job.stage_detail && <span className="ml-2 text-xs text-muted-foreground">{job.stage_detail}</span>}
      </TableCell>
      <TableCell className="text-sm tabular-nums">{job.sections_detected}</TableCell>
      <TableCell className="text-sm tabular-nums">{job.questions_generated}</TableCell>
      <TableCell className="text-sm tabular-nums">{job.knowledge_units_created}</TableCell>
      <TableCell className="text-sm tabular-nums">{job.visual_assets_detected}</TableCell>
      <TableCell className="text-xs text-muted-foreground">{new Date(job.created_at).toLocaleString()}</TableCell>
    </TableRow>
  );
}

export default function IngestionUploadPage() {
  const queryClient = useQueryClient();
  const [subjectId, setSubjectId] = useState<string | null>(null);
  const [chapterCode, setChapterCode] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<IngestionJobStatus | "">("");
  const [page, setPage] = useState(0);

  const subjectsQuery = useQuery({ queryKey: ["academic", "subjects"], queryFn: academicApi.subjects });
  const chaptersQuery = useQuery({
    queryKey: ["academic", "chapters", subjectId],
    queryFn: () => academicApi.chapters(subjectId!),
    enabled: !!subjectId,
  });

  // Small, unpaginated poll — only used to find the just-started job for the
  // live progress banner above the table.
  const jobsQuery = useQuery({
    queryKey: ["ingestion", "jobs"],
    queryFn: ingestionApi.jobs,
    refetchInterval: (query) => {
      const jobs = query.state.data ?? [];
      const stillRunning = jobs.some((j) => !TERMINAL_STATUSES.includes(j.status));
      return stillRunning ? 2500 : false;
    },
  });

  const jobsTableQuery = useQuery({
    queryKey: ["ingestion", "jobs-table", statusFilter, page],
    queryFn: () => ingestionApi.jobsPaginated({ status: statusFilter || undefined, limit: JOB_PAGE_SIZE, offset: page * JOB_PAGE_SIZE }),
    refetchInterval: (query) => {
      const jobs = query.state.data?.data ?? [];
      const stillRunning = jobs.some((j) => !TERMINAL_STATUSES.includes(j.status));
      return stillRunning ? 2500 : false;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => ingestionApi.upload(file!, chapterCode),
    onSuccess: (job) => {
      setActiveJobId(job.id);
      queryClient.invalidateQueries({ queryKey: ["ingestion", "jobs"] });
      queryClient.invalidateQueries({ queryKey: ["ingestion", "jobs-table"] });
      setFile(null);
    },
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !chapterCode) return;
    uploadMutation.mutate();
  };

  const activeJob = jobsQuery.data?.find((j) => j.id === activeJobId);

  return (
    <main className="flex flex-1 flex-col items-center gap-6 px-6 py-10">
      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle>Upload a PDF for ingestion</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            {uploadMutation.isError && (
              <Alert variant="destructive">
                <AlertDescription>
                  {uploadMutation.error instanceof ApiError ? uploadMutation.error.message : "Upload failed"}
                </AlertDescription>
              </Alert>
            )}

            <div className="flex flex-col gap-1.5">
              <Label>Subject</Label>
              <select
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={subjectId ?? ""}
                onChange={(e) => {
                  setSubjectId(e.target.value || null);
                  setChapterCode("");
                }}
              >
                <option value="">Select a subject…</option>
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
                value={chapterCode}
                onChange={(e) => setChapterCode(e.target.value)}
                disabled={!subjectId}
              >
                <option value="">Select a chapter…</option>
                {chaptersQuery.data?.map((c) => (
                  <option key={c.id} value={c.code}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pdf-file">PDF file</Label>
              <input
                id="pdf-file"
                type="file"
                accept="application/pdf"
                className="text-sm file:mr-3 file:rounded-md file:border file:bg-secondary file:px-3 file:py-1.5 file:text-sm file:font-medium"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>

            <Button type="submit" disabled={!file || !chapterCode || uploadMutation.isPending} className="mt-2 w-fit">
              {uploadMutation.isPending ? "Uploading…" : "Upload and start ingestion"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {activeJob && (
        <Card className="w-full max-w-2xl border-primary/40">
          <CardHeader>
            <CardTitle className="text-base">
              {activeJob.original_filename} — <Badge variant={STATUS_VARIANT[activeJob.status]}>{activeJob.status}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <div className="text-muted-foreground">Sections</div>
              <div className="text-lg font-semibold tabular-nums">{activeJob.sections_detected}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Questions</div>
              <div className="text-lg font-semibold tabular-nums">{activeJob.questions_generated}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Knowledge Units</div>
              <div className="text-lg font-semibold tabular-nums">{activeJob.knowledge_units_created}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Visual Assets</div>
              <div className="text-lg font-semibold tabular-nums">{activeJob.visual_assets_detected}</div>
            </div>
            {activeJob.stage_detail && (
              <div className="col-span-2 sm:col-span-4 text-xs text-muted-foreground">{activeJob.stage_detail}</div>
            )}
            {activeJob.error_message && (
              <Alert variant="destructive" className="col-span-2 sm:col-span-4">
                <AlertDescription>{activeJob.error_message}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="w-full max-w-4xl">
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">Recent ingestion jobs</CardTitle>
          <select
            className="h-8 rounded-md border bg-background px-2 text-sm"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as IngestionJobStatus | "");
              setPage(0);
            }}
          >
            <option value="">All statuses</option>
            {Object.keys(STATUS_VARIANT).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {jobsTableQuery.data && jobsTableQuery.data.data.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>File</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Sections</TableHead>
                    <TableHead>Questions</TableHead>
                    <TableHead>Knowledge Units</TableHead>
                    <TableHead>Visual Assets</TableHead>
                    <TableHead>Started</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jobsTableQuery.data.data.map((job) => (
                    <JobRow key={job.id} job={job} />
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <EmptyState title="No ingestion jobs match this filter" description="Upload a PDF above to run the pipeline for the first time." />
          )}

          {jobsTableQuery.data && jobsTableQuery.data.meta.total > JOB_PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                <ChevronLeft className="size-4" aria-hidden="true" /> Previous
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {page + 1} of {Math.max(1, Math.ceil(jobsTableQuery.data.meta.total / JOB_PAGE_SIZE))} · {jobsTableQuery.data.meta.total} total
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={(page + 1) * JOB_PAGE_SIZE >= jobsTableQuery.data.meta.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next <ChevronRight className="size-4" aria-hidden="true" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
