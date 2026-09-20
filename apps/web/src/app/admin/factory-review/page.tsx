"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { cmsApi } from "@/features/cms/api";

type QueueRow = {
  factory_review_item_id: string;
  content_item_id: string | null;
  selection_class: string;
  selection_reason: string | null;
  review_status: string;
  qa_classification: string | null;
  title: string | null;
  ecaep_status: string | null;
  difficulty: string | null;
  model_used: string | null;
  provider?: string | null;
  prompt_version?: string | null;
  failed_checks: string[];
  quarantine: boolean;
};

const CLASS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  GREEN_SAMPLE: "default",
  YELLOW: "secondary",
  RED: "destructive",
};

export default function FactoryReviewPage() {
  const queryClient = useQueryClient();
  const [selectionClass, setSelectionClass] = useState<string>("");
  const [needsReview, setNeedsReview] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [failureReasons, setFailureReasons] = useState<string[]>([]);

  const dashQuery = useQuery({
    queryKey: ["cms", "factory-review-dashboard"],
    queryFn: () => cmsApi.factoryReviewDashboard(),
  });

  const queueQuery = useQuery({
    queryKey: ["cms", "factory-review-queue", selectionClass, needsReview],
    queryFn: () =>
      cmsApi.factoryReviewQueue({
        selection_class: selectionClass || undefined,
        needs_review: needsReview,
        sort: "risk",
        limit: 50,
      }),
  });

  const packetQuery = useQuery({
    queryKey: ["cms", "factory-review-packet", activeId],
    queryFn: () => cmsApi.factoryReviewPacket(activeId!),
    enabled: Boolean(activeId),
  });

  const decisionMutation = useMutation({
    mutationFn: (decision: "ACCEPT" | "CORRECTION_REQUIRED" | "REJECT") =>
      cmsApi.factoryReviewDecision(activeId!, {
        decision,
        checklist: checked,
        failure_reasons: failureReasons,
        reviewer_note: note || undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cms", "factory-review-queue"] });
      queryClient.invalidateQueries({ queryKey: ["cms", "factory-review-dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["cms", "factory-review-packet", activeId] });
      setNote("");
    },
  });

  const rows = (queueQuery.data?.data ?? []) as QueueRow[];
  const dash = dashQuery.data as Record<string, number | string> | undefined;
  const packet = packetQuery.data as Record<string, unknown> | undefined;
  const checklistTemplate = (packet?.human_checklist_template as { id: string; category: string; prompt: string }[]) ?? [];
  const taxonomy = (packet?.failure_reason_taxonomy as string[]) ?? [];
  const question = packet?.question as Record<string, unknown> | undefined;
  const autoQa = packet?.automated_qa as Record<string, unknown> | undefined;

  const options = useMemo(() => {
    const opts = (question?.options as { label: string; text: string }[]) ?? [];
    return opts;
  }, [question]);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Factory Review</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Human sampling and exception review for AI-generated DRAFTs. Factory ACCEPT does not approve or publish —
          use ECAEP separately.
        </p>
      </div>

      <Alert>
        <AlertDescription>
          Automated QA is <strong>not</strong> scientific certification. Sample acceptance does not imply the full
          batch is scientifically correct.
        </AlertDescription>
      </Alert>

      {dashQuery.isLoading ? (
        <Skeleton className="h-28 w-full" />
      ) : dash ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Pilot progress</CardTitle>
            <CardDescription>{String(dash.disclaimer ?? "")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2 text-sm">
            <Badge variant="outline">Candidates {String(dash.total_candidates ?? 0)}</Badge>
            <Badge variant="default">GREEN {String(dash.GREEN ?? 0)}</Badge>
            <Badge variant="secondary">YELLOW {String(dash.YELLOW ?? 0)}</Badge>
            <Badge variant="destructive">RED {String(dash.RED ?? 0)}</Badge>
            <Badge variant="outline">
              GREEN sampled {String(dash.green_accepted ?? 0)}/{String(dash.green_sampled ?? 0)} accepted
            </Badge>
            <Badge variant="outline">
              YELLOW {String(dash.yellow_accepted ?? 0)}/{String(dash.yellow_total_in_queue ?? 0)}
            </Badge>
            <Badge variant="outline">
              RED {String(dash.red_accepted ?? 0)}/{String(dash.red_total_in_queue ?? 0)}
            </Badge>
            <Badge variant="secondary">
              Pending G/Y/R {String(dash.green_pending ?? 0)}/{String(dash.yellow_pending ?? 0)}/
              {String(dash.red_pending ?? 0)}
            </Badge>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Review queue</CardTitle>
            <CardDescription>Sorted by risk (RED → YELLOW → GREEN sample). Reasons shown per row.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="h-9 rounded-md border bg-background px-2 text-sm"
                value={selectionClass}
                onChange={(e) => setSelectionClass(e.target.value)}
              >
                <option value="">All classes</option>
                <option value="GREEN_SAMPLE">GREEN sample</option>
                <option value="YELLOW">YELLOW</option>
                <option value="RED">RED</option>
              </select>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={needsReview} onChange={(e) => setNeedsReview(e.target.checked)} />
                Needs review
              </label>
            </div>

            {queueQuery.isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : rows.length === 0 ? (
              <EmptyState
                icon={ClipboardCheck}
                title="No factory review items"
                description="Create a sample after P4 QA, or clear filters."
              />
            ) : (
              <ul className="divide-y rounded-md border">
                {rows.map((row) => (
                  <li key={row.factory_review_item_id}>
                    <button
                      type="button"
                      className="flex w-full flex-col gap-1 px-3 py-3 text-left hover:bg-muted/40"
                      onClick={() => {
                        setActiveId(row.factory_review_item_id);
                        setChecked({});
                        setFailureReasons([]);
                        setNote("");
                      }}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={CLASS_VARIANT[row.selection_class] ?? "outline"}>{row.selection_class}</Badge>
                        <Badge variant="outline">{row.review_status}</Badge>
                        {row.quarantine ? <Badge variant="destructive">Quarantine</Badge> : null}
                        {row.difficulty ? <Badge variant="outline">{row.difficulty}</Badge> : null}
                      </div>
                      <p className="text-sm font-medium">{row.title ?? "Untitled draft"}</p>
                      <p className="text-xs text-muted-foreground">
                        {row.selection_reason ?? "—"} · ECAEP {row.ecaep_status ?? "—"} ·{" "}
                        {(row.provider ? `${row.provider} / ` : "") + (row.model_used ?? "model n/a")}
                        {row.prompt_version ? ` · ${row.prompt_version}` : ""}
                      </p>
                      {row.failed_checks?.length ? (
                        <p className="text-[11px] text-muted-foreground">Failed: {row.failed_checks.slice(0, 4).join(", ")}</p>
                      ) : null}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Review packet</CardTitle>
            <CardDescription>Human checklist evidence — does not auto-submit to ECAEP.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!activeId ? (
              <p className="text-sm text-muted-foreground">Select a queue item to inspect.</p>
            ) : packetQuery.isLoading ? (
              <Skeleton className="h-64 w-full" />
            ) : packet ? (
              <>
                <Alert>
                  <AlertDescription>{String(autoQa?.label ?? "Automated QA — NOT scientific certification")}</AlertDescription>
                </Alert>
                <div className="space-y-1 text-sm">
                  <p>
                    <span className="text-muted-foreground">QA:</span> {String(autoQa?.classification ?? "—")} ·{" "}
                    {String(autoQa?.qa_version ?? "")}
                  </p>
                  <p>
                    <span className="text-muted-foreground">Duplicate:</span> {String(autoQa?.duplicate_class ?? "—")}
                  </p>
                  <p className="text-xs text-muted-foreground">{String(packet.ecaep_note ?? "")}</p>
                </div>

                <div className="rounded-md border p-3 text-sm">
                  <p className="font-medium">{String(question?.stem ?? "")}</p>
                  <ul className="mt-2 space-y-1">
                    {options.map((o) => (
                      <li key={o.label}>
                        <strong>{o.label}.</strong> {o.text}
                        {question?.correct_option === o.label ? " ✓" : ""}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-muted-foreground">{String(question?.explanation ?? "")}</p>
                </div>

                {(packet.generation_lineage as { content_item_id?: string } | undefined)?.content_item_id ? (
                  <Link
                    href={`/admin/content/${(packet.generation_lineage as { content_item_id?: string }).content_item_id}`}
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex")}
                  >
                    Open ECAEP content item
                  </Link>
                ) : null}

                <div className="space-y-2">
                  <p className="text-sm font-medium">Human checklist</p>
                  {checklistTemplate.map((row) => (
                    <label key={row.id} className="flex items-start gap-2 text-sm">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={Boolean(checked[row.id])}
                        onChange={() => setChecked((c) => ({ ...c, [row.id]: !c[row.id] }))}
                      />
                      <span>
                        <span className="font-medium">{row.category}</span> — {row.prompt}
                      </span>
                    </label>
                  ))}
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium">Failure reasons</p>
                  <div className="flex flex-wrap gap-2">
                    {taxonomy.map((r) => (
                      <label key={r} className="flex items-center gap-1 text-xs">
                        <input
                          type="checkbox"
                          checked={failureReasons.includes(r)}
                          onChange={() =>
                            setFailureReasons((prev) =>
                              prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r],
                            )
                          }
                        />
                        {r}
                      </label>
                    ))}
                  </div>
                </div>

                <textarea
                  className="min-h-20 w-full rounded-md border bg-background p-2 text-sm"
                  placeholder="Reviewer note (required for CORRECTION_REQUIRED / REJECT)"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />

                {decisionMutation.isError ? (
                  <Alert variant="destructive">
                    <AlertDescription>
                      {decisionMutation.error instanceof ApiError
                        ? decisionMutation.error.message
                        : "Decision failed"}
                    </AlertDescription>
                  </Alert>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    disabled={decisionMutation.isPending}
                    onClick={() => decisionMutation.mutate("ACCEPT")}
                  >
                    Accept (factory only)
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={decisionMutation.isPending}
                    onClick={() => decisionMutation.mutate("CORRECTION_REQUIRED")}
                  >
                    Correction required
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={decisionMutation.isPending}
                    onClick={() => decisionMutation.mutate("REJECT")}
                  >
                    Reject
                  </Button>
                </div>
              </>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
