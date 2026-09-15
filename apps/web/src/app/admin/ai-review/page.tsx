"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ClipboardList } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { academicApi } from "@/features/academic/api";
import { cmsApi, type EditorialCampaign, type WorkflowState } from "@/features/cms/api";
import {
  DEFAULT_ECAEP_FILTERS,
  ECAEP_WORKFLOW_STATUSES,
  ecaepFilterSummary,
  ecaepFiltersToApiParams,
  ecaepFiltersToSearchParams,
  parseEcaepFilters,
  type EcaepQueueFilters,
} from "@/features/cms/ecaep-queue-filters";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;

const selectClass =
  "h-9 rounded-md border bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

const STATE_VARIANT: Record<WorkflowState, "default" | "secondary" | "outline" | "destructive"> = {
  DRAFT: "outline",
  IN_REVIEW: "secondary",
  CHANGES_REQUESTED: "destructive",
  APPROVED: "secondary",
  PUBLISHED: "default",
  ARCHIVED: "outline",
};

function ProgressBar({ published, target }: { published: number; target: number }) {
  const pct = Math.min(100, Math.round((published / Math.max(1, target)) * 100));
  return (
    <div className="space-y-1">
      <div className="flex h-2 overflow-hidden rounded-sm bg-muted" role="progressbar" aria-valuenow={published} aria-valuemax={target}>
        <div className="bg-foreground/70 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <p className="text-xs text-muted-foreground">
        {published} / {target} published (planning target — quality over quantity)
      </p>
    </div>
  );
}

function CampaignOverview({ data }: { data: EditorialCampaign }) {
  const notableChapters = useMemo(() => {
    const high = data.chapter_coverage.filter((c) => c.concentration === "high").slice(0, 6);
    const gaps = data.chapter_coverage
      .filter((c) => c.concentration === "low_published" && (c.draft > 0 || c.in_review > 0 || c.review_queue > 0))
      .slice(0, 8);
    return { high, gaps };
  }, [data.chapter_coverage]);

  const tableRows = useMemo(() => {
    return [...data.chapter_coverage]
      .filter((c) => c.published > 0 || c.review_queue > 0 || c.draft > 0)
      .sort((a, b) => b.draft + b.in_review - (a.draft + a.in_review) || a.published - b.published)
      .slice(0, 24);
  }, [data.chapter_coverage]);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Content campaign (planning targets)</CardTitle>
          <CardDescription>
            Human review remains mandatory. Progress bars are planning aids — do not publish low-quality items to
            inflate counts. Biology = Botany + Zoology. Pipeline and subject inventory counts are complete DB
            aggregates (not a first-N scan).
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          {data.targets.map((t) => (
            <div key={t.area} className="space-y-2 rounded-md border p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="font-medium">{t.area}</p>
                <Badge variant={t.met_planning_target ? "default" : "outline"}>
                  {t.remaining === 0 ? "Target met" : `${t.remaining} remaining`}
                </Badge>
              </div>
              <ProgressBar published={t.published} target={t.target} />
              <p className="text-xs text-muted-foreground">
                Complete pipeline: {t.pipeline.draft} draft · {t.pipeline.in_review} in review ·{" "}
                {t.pipeline.approved} approved
                {t.pipeline_complete === false ? " (partial)" : ""}
              </p>
              <p className="text-[11px] text-muted-foreground">Includes: {t.subjects_included.join(", ")}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Inventory snapshot (complete totals)</CardTitle>
          <CardDescription>
            {data.count_semantics?.status_counts ??
              "Total matching QUESTION rows by workflow status — complete inventory, not a sample."}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2 text-sm">
          <Badge variant="outline">Total DRAFT {data.status_counts.draft}</Badge>
          <Badge variant="secondary">Total IN_REVIEW {data.status_counts.in_review}</Badge>
          <Badge variant="secondary">Total APPROVED {data.status_counts.approved}</Badge>
          <Badge variant="default">Total PUBLISHED {data.status_counts.published}</Badge>
          <Badge variant="destructive">Needs changes {data.status_counts.changes_requested}</Badge>
          <Badge variant="outline">Missing provenance (complete) {data.status_counts.missing_provenance}</Badge>
          <Badge variant="outline">Missing mapping (complete) {data.status_counts.missing_mapping}</Badge>
          <Badge variant="outline">
            Structurally invalid (sample) {data.status_counts.structurally_invalid}
          </Badge>
        </CardContent>
      </Card>

      {data.by_academic_subject?.length ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">By academic subject (complete)</CardTitle>
            <CardDescription>
              {data.count_semantics?.by_academic_subject ??
                "Full SQL GROUP BY subject × status — includes Zoology IN_REVIEW without scan caps."}
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted text-left">
                <tr>
                  <th className="p-2">Subject</th>
                  <th className="p-2 text-right">Draft</th>
                  <th className="p-2 text-right">In review</th>
                  <th className="p-2 text-right">Approved</th>
                  <th className="p-2 text-right">Published</th>
                </tr>
              </thead>
              <tbody>
                {data.by_academic_subject.map((row) => (
                  <tr key={row.subject} className="border-t">
                    <td className="p-2">{row.subject}</td>
                    <td className="p-2 text-right">{row.draft}</td>
                    <td className="p-2 text-right">{row.in_review}</td>
                    <td className="p-2 text-right">{row.approved}</td>
                    <td className="p-2 text-right">{row.published}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Quality metrics (structural sample)</CardTitle>
          <CardDescription>{data.quality_metrics.disclaimer}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
          <p>% with provenance: {data.quality_metrics.pct_with_provenance}</p>
          <p>% with academic mapping: {data.quality_metrics.pct_with_academic_mapping}</p>
          <p>% with explanations: {data.quality_metrics.pct_with_explanation}</p>
          <p>% structurally valid: {data.quality_metrics.pct_structurally_valid}</p>
          <p>% reviewed or beyond: {data.quality_metrics.pct_reviewed_or_beyond}</p>
          <p>% approved or published: {data.quality_metrics.pct_approved_or_published}</p>
          <p>% published: {data.quality_metrics.pct_published}</p>
          <p className="text-xs text-muted-foreground sm:col-span-2">
            Structural sample: {data.quality_metrics.total_questions_scanned}
            {data.quality_metrics.sample_limit != null
              ? ` / limit ${data.quality_metrics.sample_limit}`
              : ""}{" "}
            recent questions
            {data.quality_metrics.inventory_total_questions != null
              ? ` · inventory total ${data.quality_metrics.inventory_total_questions}`
              : ""}
            . These percentages are sample-only — not complete inventory totals. Scientific correctness is never
            inferred from these figures.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Chapter coverage</CardTitle>
          <CardDescription>
            Over-concentrated chapters and zero/low published coverage. Prefer diversification when choosing the next
            review.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {notableChapters.high.length > 0 && (
            <div className="space-y-1 text-sm">
              <p className="font-medium">High draft concentration</p>
              {notableChapters.high.map((c) => (
                <p key={c.chapter_id} className="text-muted-foreground">
                  {c.subject_name} · {c.chapter_name} — {c.draft} draft / {c.in_review} in review / {c.published}{" "}
                  published
                </p>
              ))}
            </div>
          )}
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted text-left">
                <tr>
                  <th className="p-2">Subject</th>
                  <th className="p-2">Chapter</th>
                  <th className="p-2 text-right">Published</th>
                  <th className="p-2 text-right">Review queue</th>
                  <th className="p-2 text-right">Draft</th>
                  <th className="p-2">Flag</th>
                </tr>
              </thead>
              <tbody>
                {tableRows.map((c) => (
                  <tr key={c.chapter_id} className="border-t">
                    <td className="p-2">{c.subject_name}</td>
                    <td className="p-2">{c.chapter_name}</td>
                    <td className="p-2 text-right">{c.published}</td>
                    <td className="p-2 text-right">{c.review_queue}</td>
                    <td className="p-2 text-right">{c.draft}</td>
                    <td className="p-2">
                      {c.concentration === "high" && <Badge variant="destructive">Concentrated</Badge>}
                      {c.concentration === "low_published" && <Badge variant="outline">Low published</Badge>}
                      {c.concentration === "normal" && <span className="text-muted-foreground">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/** Page-local only — App Router forbids named exports from page.tsx (FRONTEND-BUILD-001). */
function EditorialReviewQueueInner() {
  const searchParams = useSearchParams();

  const applied = useMemo(() => parseEcaepFilters(searchParams), [searchParams]);
  const [draft, setDraft] = useState<Omit<EcaepQueueFilters, "page">>(() => ({
    subjectName: applied.subjectName,
    status: applied.status,
    difficulty: applied.difficulty,
    provenance: applied.provenance,
    readiness: applied.readiness,
    pilotOnly: applied.pilotOnly,
    batchAOnly: applied.batchAOnly,
  }));

  useEffect(() => {
    setDraft({
      subjectName: applied.subjectName,
      status: applied.status,
      difficulty: applied.difficulty,
      provenance: applied.provenance,
      readiness: applied.readiness,
      pilotOnly: applied.pilotOnly,
      batchAOnly: applied.batchAOnly,
    });
  }, [
    applied.subjectName,
    applied.status,
    applied.difficulty,
    applied.provenance,
    applied.readiness,
    applied.pilotOnly,
    applied.batchAOnly,
  ]);

  const applyHref = useMemo(() => {
    const qs = ecaepFiltersToSearchParams({ ...draft, page: 0 }).toString();
    return qs ? `/admin/ai-review?${qs}` : "/admin/ai-review";
  }, [draft]);

  const resetHref = useMemo(() => {
    const qs = ecaepFiltersToSearchParams(DEFAULT_ECAEP_FILTERS).toString();
    return qs ? `/admin/ai-review?${qs}` : "/admin/ai-review";
  }, []);

  const pageHref = (page: number) => {
    const qs = ecaepFiltersToSearchParams({ ...applied, page }).toString();
    return qs ? `/admin/ai-review?${qs}` : "/admin/ai-review";
  };

  const apiFilters = useMemo(
    () => ecaepFiltersToApiParams(applied, PAGE_SIZE),
    [applied],
  );

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["cms", "editorial-review-queue", apiFilters],
    queryFn: () => cmsApi.editorialReviewQueue(apiFilters),
  });

  const { data: campaign, isLoading: campaignLoading, isError: campaignError } = useQuery({
    queryKey: ["cms", "editorial-campaign"],
    queryFn: () => cmsApi.editorialCampaign(),
  });

  const { data: pilot } = useQuery({
    queryKey: ["cms", "editorial-batch-a-pilot"],
    queryFn: () => cmsApi.batchAPilot(),
  });

  const { data: subjects } = useQuery({
    queryKey: ["academic", "subjects"],
    queryFn: () => academicApi.subjects(),
    staleTime: 60_000,
  });

  const items = data?.data ?? [];
  const total = data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const recommended = data?.meta.recommended_next;
  const summary = ecaepFilterSummary(applied);

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">ECAEP · Human campaign</p>
          <h1 className="font-heading flex items-center gap-2 text-xl font-semibold">
            <ClipboardList className="size-5" aria-hidden="true" />
            Editorial Review & Campaign
          </h1>
          <p className="text-sm text-muted-foreground">
            Filter by subject and workflow status. Open a packet for human review — do not mass-approve or
            mass-publish. AI flags are assistance only.
          </p>
        </div>

        {pilot && (
          <Alert>
            <AlertDescription className="space-y-2 text-sm">
              <p>
                <span className="font-medium">Batch A SME pilot</span> ({pilot.pilot_id}): {pilot.selected_count}{" "}
                selected · {pilot.batch_a_total} Batch A total · {pilot.remaining_batch_a_untouched} held back until
                pilot evaluation.
              </p>
              <p className="text-xs text-muted-foreground">
                Subjects:{" "}
                {Object.entries(pilot.distributions.subject)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(" · ")}
                {" · "}Difficulty:{" "}
                {Object.entries(pilot.distributions.difficulty)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(", ")}
              </p>
              <p className="text-xs text-muted-foreground">
                Target is “review and publish only what passes human judgement” — not “publish 40.”
              </p>
            </AlertDescription>
          </Alert>
        )}

        {campaignLoading ? <Skeleton className="h-48 w-full" /> : null}
        {campaignError ? (
          <Alert variant="destructive">
            <AlertTitle>Campaign dashboard unavailable</AlertTitle>
            <AlertDescription>Queue filters below still work independently.</AlertDescription>
          </Alert>
        ) : null}
        {campaign ? <CampaignOverview data={campaign} /> : null}

        {recommended && applied.page === 0 && (
          <Alert>
            <AlertDescription>
              <span className="font-medium">Recommended next review: </span>
              <Link href={`/admin/content/${recommended.id}`} className="underline underline-offset-2">
                {recommended.title}
              </Link>
              <ul className="mt-2 list-inside list-disc text-xs text-muted-foreground">
                {recommended.priority_reasons.slice(0, 4).map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        <section
          className="space-y-3 rounded-lg border bg-card p-4"
          aria-labelledby="ecaep-filters-heading"
        >
          <div className="flex flex-wrap items-end justify-between gap-2">
            <h2 id="ecaep-filters-heading" className="text-sm font-semibold">
              Queue filters
            </h2>
            <p className="text-xs text-muted-foreground" aria-live="polite" data-testid="ecaep-filter-summary">
              {summary}
              {data ? ` · ${total.toLocaleString()} matching` : null}
              {items.length > 0
                ? ` · displaying ${items.length} on page ${applied.page + 1} of ${totalPages}`
                : null}
            </p>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label htmlFor="ecaep-subject">Subject</Label>
              <select
                id="ecaep-subject"
                className={selectClass}
                data-testid="ecaep-subject-filter"
                value={draft.subjectName}
                onChange={(e) => setDraft((d) => ({ ...d, subjectName: e.target.value }))}
              >
                <option value="">All subjects</option>
                {(subjects ?? [])
                  .slice()
                  .sort((a, b) => a.display_order - b.display_order || a.name.localeCompare(b.name))
                  .map((s) => (
                    <option key={s.id} value={s.name}>
                      {s.name}
                    </option>
                  ))}
              </select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="ecaep-status">Status</Label>
              <select
                id="ecaep-status"
                className={selectClass}
                data-testid="ecaep-status-filter"
                value={draft.status}
                onChange={(e) => setDraft((d) => ({ ...d, status: e.target.value }))}
              >
                {ECAEP_WORKFLOW_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="ecaep-difficulty">Difficulty</Label>
              <select
                id="ecaep-difficulty"
                className={selectClass}
                aria-label="Filter by difficulty"
                value={draft.difficulty}
                onChange={(e) => setDraft((d) => ({ ...d, difficulty: e.target.value }))}
              >
                <option value="">Any difficulty</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="ecaep-provenance">Provenance</Label>
              <select
                id="ecaep-provenance"
                className={selectClass}
                aria-label="Filter by provenance"
                value={draft.provenance}
                onChange={(e) => setDraft((d) => ({ ...d, provenance: e.target.value }))}
              >
                <option value="">Any provenance</option>
                <option value="known">Known lineage</option>
                <option value="missing">Missing lineage</option>
              </select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="ecaep-readiness">Readiness</Label>
              <select
                id="ecaep-readiness"
                className={selectClass}
                aria-label="Filter by review readiness"
                value={draft.readiness}
                onChange={(e) => setDraft((d) => ({ ...d, readiness: e.target.value }))}
              >
                <option value="">Any readiness</option>
                <option value="structurally_ready">Structurally ready</option>
                <option value="needs_work">Needs structural work</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label className="flex h-9 items-center gap-2 rounded-md border px-2 text-sm">
              <input
                type="checkbox"
                checked={draft.pilotOnly}
                onChange={(e) => setDraft((d) => ({ ...d, pilotOnly: e.target.checked }))}
              />
              Batch A pilot (~40)
            </label>
            <label className="flex h-9 items-center gap-2 rounded-md border px-2 text-sm">
              <input
                type="checkbox"
                checked={draft.batchAOnly}
                onChange={(e) => setDraft((d) => ({ ...d, batchAOnly: e.target.checked }))}
              />
              Batch A only
            </label>
            <Link
              href={applyHref}
              className={cn(buttonVariants({ size: "sm" }))}
              data-testid="ecaep-apply-filters"
            >
              Apply filters
            </Link>
            <Link
              href={resetHref}
              className={cn(buttonVariants({ size: "sm", variant: "outline" }))}
              data-testid="ecaep-reset-filters"
            >
              Reset
            </Link>
          </div>
        </section>

        {data?.meta.prioritization && <p className="text-xs text-muted-foreground">{data.meta.prioritization}</p>}
        {data?.meta.quality_vs_science && <p className="text-xs text-muted-foreground">{data.meta.quality_vs_science}</p>}

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Queue failed to load</AlertTitle>
            <AlertDescription>
              Could not load the review queue. Check that your account has content.review.
            </AlertDescription>
          </Alert>
        )}

        {isLoading ? (
          <div className="flex flex-col gap-2" aria-busy="true" role="status" aria-label="Loading review queue">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : items.length === 0 && !error ? (
          <EmptyState
            title="Nothing in this queue filter"
            description={`No items match ${summary}. Clear Batch A / pilot gates or reset filters. Human approval remains mandatory.`}
          />
        ) : items.length > 0 ? (
          <div className="grid gap-3">
            {items.map((item) => (
              <Link key={item.id} href={`/admin/content/${item.id}`}>
                <Card className="transition-colors hover:bg-muted/50">
                  <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
                    <div className="space-y-1">
                      <CardTitle className="text-base">{item.title}</CardTitle>
                      <p className="text-xs text-muted-foreground">
                        {[item.academic.subject?.name, item.academic.chapter?.name, item.academic.topic?.name]
                          .filter(Boolean)
                          .join(" · ") || "Unmapped"}
                        {item.difficulty ? ` · ${item.difficulty}` : ""}
                        {item.campaign_area ? ` · ${item.campaign_area}` : ""}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <Badge variant={STATE_VARIANT[item.status]}>{item.status}</Badge>
                      {item.batch_a && <Badge variant="outline">Human-authored Batch A</Badge>}
                      <Badge variant={item.structural.review_ready ? "default" : "outline"}>
                        {item.structural.review_ready ? "Structurally ready" : "Needs work"}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2 pt-0 text-xs text-muted-foreground">
                    <div className="flex flex-wrap gap-2">
                      <span>Provenance: {item.provenance.label ?? item.provenance.status}</span>
                      <span>Explanation: {item.explanation_present ? "present" : "missing"}</span>
                      {item.chapter_inventory && (
                        <span>
                          Chapter: {item.chapter_inventory.published} published / {item.chapter_inventory.draft} draft
                        </span>
                      )}
                      {item.ai_check_flags.length > 0 && (
                        <Badge variant="destructive">{item.ai_check_flags.length} AI flag(s) (assist only)</Badge>
                      )}
                    </div>
                    {item.priority_reasons && item.priority_reasons.length > 0 && (
                      <ul className="list-inside list-disc">
                        {item.priority_reasons.slice(0, 3).map((r) => (
                          <li key={r}>{r}</li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        ) : null}

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between">
            {applied.page === 0 || isFetching ? (
              <Button variant="outline" size="sm" disabled>
                <ChevronLeft className="size-4" aria-hidden="true" /> Previous
              </Button>
            ) : (
              <Link href={pageHref(applied.page - 1)} className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                <ChevronLeft className="size-4" aria-hidden="true" /> Previous
              </Link>
            )}
            <span className="text-xs text-muted-foreground">
              Page {applied.page + 1} of {totalPages} · {total} total matching
            </span>
            {applied.page >= totalPages - 1 || isFetching ? (
              <Button variant="outline" size="sm" disabled>
                Next <ChevronRight className="size-4" aria-hidden="true" />
              </Button>
            ) : (
              <Link href={pageHref(applied.page + 1)} className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
                Next <ChevronRight className="size-4" aria-hidden="true" />
              </Link>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

export default function EditorialReviewQueuePage() {
  return (
    <Suspense
      fallback={
        <main className="flex-1 px-4 py-8 sm:px-6">
          <Skeleton className="mx-auto h-96 max-w-5xl w-full" />
        </main>
      }
    >
      <EditorialReviewQueueInner />
    </Suspense>
  );
}
