"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { cmsApi, type ReviewChecklistItem } from "@/features/cms/api";

function Checklist({
  items,
  checked,
  onToggle,
}: {
  items: ReviewChecklistItem[];
  checked: Record<string, boolean>;
  onToggle: (id: string) => void;
}) {
  const byCategory = useMemo(() => {
    const map = new Map<string, ReviewChecklistItem[]>();
    for (const item of items) {
      const list = map.get(item.category) ?? [];
      list.push(item);
      map.set(item.category, list);
    }
    return map;
  }, [items]);

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-muted-foreground">
        Checklist assists the reviewer. Checking boxes does <strong>not</strong> certify the question or authorize
        publish.
      </p>
      {[...byCategory.entries()].map(([category, rows]) => (
        <div key={category} className="space-y-2">
          <p className="text-sm font-medium">{category}</p>
          <ul className="space-y-2">
            {rows.map((row) => (
              <li key={row.id} className="flex items-start gap-2 text-sm">
                <input
                  id={`check-${row.id}`}
                  type="checkbox"
                  className="mt-1 size-4"
                  checked={Boolean(checked[row.id])}
                  onChange={() => onToggle(row.id)}
                />
                <label htmlFor={`check-${row.id}`} className="leading-snug text-muted-foreground">
                  {row.prompt}
                </label>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export default function ContentDetailPage() {
  const { itemId } = useParams<{ itemId: string }>();
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [ackChecklist, setAckChecklist] = useState(false);

  const itemQuery = useQuery({
    queryKey: ["cms", "item", itemId],
    queryFn: () => cmsApi.get(itemId),
  });

  const packetQuery = useQuery({
    queryKey: ["cms", "review-packet", itemId],
    queryFn: () => cmsApi.reviewPacket(itemId),
    retry: false,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["cms", "item", itemId] });
    queryClient.invalidateQueries({ queryKey: ["cms", "review-packet", itemId] });
    queryClient.invalidateQueries({ queryKey: ["cms", "editorial-review-queue"] });
  };

  const submitMutation = useMutation({ mutationFn: () => cmsApi.submit(itemId), onSuccess: invalidate });
  const approveMutation = useMutation({
    mutationFn: () => cmsApi.review(itemId, { decision: "approve", comment: comment || undefined }),
    onSuccess: invalidate,
  });
  const requestChangesMutation = useMutation({
    mutationFn: () => cmsApi.review(itemId, { decision: "request_changes", comment: comment || undefined }),
    onSuccess: invalidate,
  });
  const publishMutation = useMutation({ mutationFn: () => cmsApi.publish(itemId), onSuccess: invalidate });
  const archiveMutation = useMutation({ mutationFn: () => cmsApi.archive(itemId), onSuccess: invalidate });

  const item = itemQuery.data;
  const packet = packetQuery.data;
  const isLoading = itemQuery.isLoading;
  const error = itemQuery.error;

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }
  if (error instanceof ApiError && error.status === 404) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Not found.</main>;
  }
  if (!item) return null;

  const anyPending =
    submitMutation.isPending ||
    approveMutation.isPending ||
    requestChangesMutation.isPending ||
    publishMutation.isPending ||
    archiveMutation.isPending;
  const lastError = [submitMutation, approveMutation, requestChangesMutation, publishMutation, archiveMutation]
    .map((m) => m.error)
    .find((e): e is ApiError => e instanceof ApiError);

  const question = packet?.question;
  const checklistComplete =
    !packet?.checklist?.length || packet.checklist.every((c) => checked[c.id]) || ackChecklist;

  return (
    <main className="flex flex-1 justify-center px-4 py-10 sm:px-6">
      <div className="flex w-full max-w-3xl flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Link href="/admin/ai-review" className="text-sm text-muted-foreground underline-offset-2 hover:underline">
            ← Editorial queue
          </Link>
          <Badge>{item.status}</Badge>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{item.title}</CardTitle>
            <CardDescription>
              {item.content_type} · v{item.latest_version?.version_no}
              {packet?.academic?.subject?.name
                ? ` · ${packet.academic.subject.name} / ${packet.academic.chapter?.name ?? "—"} / ${packet.academic.topic?.name ?? "—"}`
                : item.concept_id
                  ? ` · concept ${item.concept_id.slice(0, 8)}…`
                  : " · unmapped"}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {lastError && (
              <Alert variant="destructive">
                <AlertDescription>{lastError.message}</AlertDescription>
              </Alert>
            )}

            {packet?.structural && !packet.structural.valid && (
              <Alert variant="destructive">
                <AlertDescription>
                  Structural issues: {packet.structural.issues.join("; ") || "incomplete body"}
                </AlertDescription>
              </Alert>
            )}

            {packet?.batch_a?.is_batch_a && (
              <Alert>
                <AlertDescription className="space-y-1 text-sm">
                  <p className="font-medium">{packet.batch_a.display_label} — SME review required</p>
                  <p className="text-xs text-muted-foreground">
                    Not official NTA/NCERT content. Checklist completion does not approve or publish.
                  </p>
                </AlertDescription>
              </Alert>
            )}

            {question ? (
              <div className="space-y-4 text-sm">
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Stem</p>
                  <p className="whitespace-pre-wrap leading-relaxed">{question.stem}</p>
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Options</p>
                  {question.options.map((opt) => {
                    const isCorrect = opt.label === question.correct_option;
                    return (
                      <div
                        key={opt.label}
                        className={`rounded-md border px-3 py-2 ${isCorrect ? "border-emerald-600/50 bg-emerald-500/10" : ""}`}
                      >
                        <span className="font-medium">{opt.label}.</span> {opt.text}
                        {isCorrect && (
                          <Badge className="ml-2" variant="default">
                            Correct
                          </Badge>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Explanation</p>
                  <p className="whitespace-pre-wrap text-muted-foreground">{question.explanation || "—"}</p>
                </div>
                <p className="text-xs text-muted-foreground">Difficulty: {question.difficulty ?? "—"}</p>
              </div>
            ) : (
              <pre className="overflow-x-auto rounded-md border bg-muted p-4 text-xs">
                {JSON.stringify(item.latest_version?.body, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>

        {packet && (
          <>
            <Card className={packet.provenance.source_verification_required ? "border-amber-500/40" : undefined}>
              <CardHeader>
                <CardTitle className="text-base">Provenance (as stored)</CardTitle>
                <CardDescription>
                  {packet.provenance.display_note ??
                    "Missing fields stay blank — never invent official/NTA claims."}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-1 text-sm text-muted-foreground">
                {packet.provenance.source_verification_required && (
                  <Badge variant="outline" className="w-fit">
                    Source verification required
                  </Badge>
                )}
                <p>Status: {packet.provenance.status}</p>
                <p>Model: {packet.provenance.model_used ?? "—"}</p>
                <p>Knowledge unit: {packet.provenance.knowledge_unit_id ?? "—"}</p>
                <p>Prompt version: {packet.provenance.prompt_version ?? "—"}</p>
                <p>
                  Confidence:{" "}
                  {packet.provenance.confidence_score != null
                    ? `${Math.round(packet.provenance.confidence_score * 100)}%`
                    : "—"}
                </p>
              </CardContent>
            </Card>

            {packet.structural.note && (
              <p className="text-xs text-muted-foreground">{packet.structural.note}</p>
            )}

            {packet.chapter_inventory && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Chapter inventory</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  {packet.chapter_inventory.subject_name} · {packet.chapter_inventory.chapter_name}:{" "}
                  {packet.chapter_inventory.published} published, {packet.chapter_inventory.draft} draft,{" "}
                  {packet.chapter_inventory.in_review} in review
                </CardContent>
              </Card>
            )}

            {packet.suspected_duplicates.length > 0 && (
              <Card className="border-amber-500/40">
                <CardHeader>
                  <CardTitle className="text-base">Suspected duplicates</CardTitle>
                  <CardDescription>Exact stem match. Human decides — nothing is auto-rejected.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {packet.suspected_duplicates.map((dup) => (
                    <Link key={dup.id} href={`/admin/content/${dup.id}`} className="block underline-offset-2 hover:underline">
                      {dup.title} · {dup.status}
                    </Link>
                  ))}
                </CardContent>
              </Card>
            )}

            {packet.ai_assistance.report && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">AI assistance (not certification)</CardTitle>
                  <CardDescription>{packet.ai_assistance.disclaimer}</CardDescription>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  {JSON.stringify(packet.ai_assistance.report, null, 2)}
                </CardContent>
              </Card>
            )}

            {packet.factory_qa && (
              <Card className="border-amber-500/40">
                <CardHeader>
                  <CardTitle className="text-base">Factory automated QA</CardTitle>
                  <CardDescription>{packet.factory_qa.disclaimer}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {packet.factory_qa.present ? (
                    <>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">{packet.factory_qa.classification}</Badge>
                        <Badge variant="outline">{packet.factory_qa.qa_version}</Badge>
                        {packet.factory_qa.quarantine ? <Badge variant="destructive">Quarantine</Badge> : null}
                      </div>
                      {packet.factory_qa.failed_checks?.length ? (
                        <p className="text-xs text-muted-foreground">
                          Failed: {packet.factory_qa.failed_checks.join(", ")}
                        </p>
                      ) : null}
                      <p className="text-xs text-muted-foreground">
                        Duplicate: {packet.factory_qa.duplicate_class ?? "—"} · Scientific certification: never
                      </p>
                    </>
                  ) : (
                    <p className="text-xs text-muted-foreground">No factory QAResult on this item.</p>
                  )}
                  {packet.factory_qa.factory_review ? (
                    <div className="rounded-md border p-2 text-xs">
                      <p>
                        Factory review: {packet.factory_qa.factory_review.selection_class} ·{" "}
                        {packet.factory_qa.factory_review.review_status}
                        {packet.factory_qa.factory_review.decision
                          ? ` · ${packet.factory_qa.factory_review.decision}`
                          : ""}
                      </p>
                      <Link
                        href="/admin/factory-review"
                        className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-2 inline-flex")}
                      >
                        Open Factory Review
                      </Link>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            )}

            {item.status === "IN_REVIEW" && packet.checklist.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Human review checklist</CardTitle>
                  {packet.review_notes_guidance && (
                    <CardDescription>
                      Add concise notes when useful (e.g. {packet.review_notes_guidance.examples.slice(0, 3).join("; ")}).{" "}
                      {packet.review_notes_guidance.student_visibility}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  <Checklist
                    items={packet.checklist}
                    checked={checked}
                    onToggle={(id) => setChecked((prev) => ({ ...prev, [id]: !prev[id] }))}
                  />
                  <label className="mt-4 flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      className="mt-1 size-4"
                      checked={ackChecklist}
                      onChange={(e) => setAckChecklist(e.target.checked)}
                    />
                    <span>
                      I completed (or consciously skipped) the checklist. Checking this is required before Approve —
                      checklist alone does not approve.
                    </span>
                  </label>
                </CardContent>
              </Card>
            )}

            {packet.reviews.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Prior review notes</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {packet.reviews.map((r) => (
                    <div key={r.id} className="rounded-md border px-3 py-2">
                      <p className="font-medium">
                        {r.decision} · {new Date(r.reviewed_at).toLocaleString()}
                      </p>
                      {r.comment && <p className="text-muted-foreground">{r.comment}</p>}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Actions</CardTitle>
            <CardDescription>
              Lifecycle: DRAFT → submit → IN_REVIEW → approve / request changes → APPROVED → publish → PUBLISHED
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              {item.status === "DRAFT" && (
                <Button size="sm" disabled={anyPending} onClick={() => submitMutation.mutate()}>
                  Submit for review
                </Button>
              )}

              {item.status === "IN_REVIEW" && (
                <>
                  <input
                    className="h-9 min-w-40 flex-1 rounded-md border bg-background px-2 text-sm"
                    placeholder="Review note (recommended when requesting changes)"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                  />
                  <Button
                    size="sm"
                    disabled={anyPending || !checklistComplete}
                    onClick={() => approveMutation.mutate()}
                    title={!checklistComplete ? "Acknowledge the checklist first" : undefined}
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={anyPending}
                    onClick={() => requestChangesMutation.mutate()}
                  >
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
                  Changes requested — update the draft via API or author tools, then submit again.
                </p>
              )}
            </div>
            {packet?.campaign_notes && (
              <p className="text-xs text-muted-foreground">
                Campaign target: {packet.campaign_notes.target}. Mass-publish of drafts is forbidden.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
