"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api-client";
import { cmsApi } from "@/features/cms/api";

const CHANGES_REQUESTED_REASONS = [
  "Incorrect answer",
  "Incorrect option",
  "Scientific/factual issue",
  "NCERT terminology",
  "Explanation issue",
  "Ambiguous wording",
  "Duplicate",
  "Wrong chapter/topic",
  "Other",
] as const;

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

/** HR-2.5 — maps the existing HR-2 reason labels 1:1 onto the pilot's
 * machine-readable issue codes (ANSWER..OTHER), so no UI/reason list change
 * was needed for pilot instrumentation. */
const PILOT_REASON_CODES: Record<string, string> = {
  "Incorrect answer": "ANSWER",
  "Incorrect option": "OPTION",
  "Scientific/factual issue": "SCIENCE",
  "NCERT terminology": "NCERT",
  "Explanation issue": "EXPLANATION",
  "Ambiguous wording": "AMBIGUITY",
  Duplicate: "DUPLICATE",
  "Wrong chapter/topic": "CLASSIFICATION",
  Other: "OTHER",
};

export default function ReviewSessionPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;
  const router = useRouter();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const pilotId = searchParams.get("pilot");

  const [viewIndex, setViewIndex] = useState(0);
  const [changesOpen, setChangesOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [claimWarning, setClaimWarning] = useState<string | null>(null);
  const [flagNotice, setFlagNotice] = useState<string | null>(null);

  const sessionQuery = useQuery({
    queryKey: ["cms", "review-session", sessionId],
    queryFn: () => cmsApi.getReviewSession(sessionId),
    enabled: Boolean(sessionId),
  });
  const session = sessionQuery.data;

  useEffect(() => {
    if (session) setViewIndex((v) => Math.min(v, Math.max(0, session.item_ids.length - 1)));
  }, [session]);

  useEffect(() => {
    if (session && viewIndex < session.position) {
      // Never start below the authoritative server position on first load.
    }
  }, [session, viewIndex]);

  const currentViewedItemId = session?.item_ids[viewIndex] ?? null;
  const isActionable = Boolean(session && viewIndex === session.position && session.status === "ACTIVE");

  const packetQuery = useQuery({
    queryKey: ["cms", "review-packet", currentViewedItemId],
    queryFn: () => cmsApi.reviewPacket(currentViewedItemId!),
    enabled: Boolean(currentViewedItemId),
  });
  const packet = packetQuery.data;

  // HR-2.5 pilot instrumentation — active-review-time tracking (excludes
  // time the tab was hidden/backgrounded via the Page Visibility API, the
  // only reliable "reviewer left the context" signal a browser exposes).
  // No-ops entirely when `?pilot=` isn't present, so ordinary HR-2 usage
  // (and its existing tests) are unaffected.
  const activeSpanStartRef = useRef<number | null>(null);
  const accumulatedMsRef = useRef(0);
  const reviewStartedAtRef = useRef<string | null>(null);

  useEffect(() => {
    if (!pilotId || !isActionable || !currentViewedItemId) return;
    accumulatedMsRef.current = 0;
    reviewStartedAtRef.current = new Date().toISOString();
    activeSpanStartRef.current = document.hidden ? null : Date.now();
  }, [pilotId, isActionable, currentViewedItemId]);

  useEffect(() => {
    if (!pilotId) return;
    function onVisibilityChange() {
      if (document.hidden) {
        if (activeSpanStartRef.current !== null) {
          accumulatedMsRef.current += Date.now() - activeSpanStartRef.current;
          activeSpanStartRef.current = null;
        }
      } else if (isActionable) {
        activeSpanStartRef.current = Date.now();
      }
    }
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, [pilotId, isActionable]);

  function pilotDurationSeconds(): number {
    let ms = accumulatedMsRef.current;
    if (activeSpanStartRef.current !== null) ms += Date.now() - activeSpanStartRef.current;
    return Math.round((ms / 1000) * 100) / 100;
  }

  function sendPilotEvent(decision: "APPROVED" | "CHANGES_REQUESTED" | "SKIPPED" | "FLAGGED", reasonCode?: string) {
    if (!pilotId || !currentViewedItemId) return;
    const startedAt = reviewStartedAtRef.current ?? new Date().toISOString();
    cmsApi
      .recordPilotEvent({
        pilot_id: pilotId,
        content_item_id: currentViewedItemId,
        decision,
        review_started_at: startedAt,
        decision_submitted_at: new Date().toISOString(),
        review_duration_seconds: pilotDurationSeconds(),
        subject: packet?.academic?.subject?.name ?? null,
        chapter: packet?.academic?.chapter?.name ?? null,
        reason: reasonCode ?? null,
        note: decision === "CHANGES_REQUESTED" ? note.trim() || null : null,
      })
      .catch(() => {
        // Instrumentation must never block the real review action — a
        // failed pilot-event write is surfaced in the report's total
        // count being short, not by blocking the reviewer's workflow.
      });
  }

  const claimMutation = useMutation({
    mutationFn: () => cmsApi.claimReviewItem(currentViewedItemId!, sessionId),
    onSuccess: () => setClaimWarning(null),
    onError: (err) => {
      setClaimWarning(
        err instanceof ApiError && err.code === "ALREADY_CLAIMED"
          ? "Already claimed by another active reviewer session. You may still act — backend remains authoritative."
          : err instanceof ApiError
            ? err.message
            : "Could not claim this item",
      );
    },
  });

  useEffect(() => {
    if (isActionable && currentViewedItemId) {
      claimMutation.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentViewedItemId, isActionable]);

  const advanceMutation = useMutation({
    mutationFn: () => cmsApi.advanceReviewSession(sessionId),
    onSuccess: (updated) => {
      queryClient.setQueryData(["cms", "review-session", sessionId], updated);
      setViewIndex(updated.position);
      setActionError(null);
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.message : "Failed to advance session");
    },
  });

  const approveMutation = useMutation({
    mutationFn: () => cmsApi.review(currentViewedItemId!, { decision: "approve" }),
    onSuccess: () => {
      setActionError(null);
      sendPilotEvent("APPROVED");
      advanceMutation.mutate();
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.message : "Approve failed");
    },
  });

  const changesRequestedMutation = useMutation({
    mutationFn: () =>
      cmsApi.review(currentViewedItemId!, {
        decision: "request_changes",
        comment: note.trim() ? `Reason: ${reason}. Note: ${note.trim()}` : `Reason: ${reason}`,
      }),
    onSuccess: () => {
      setActionError(null);
      sendPilotEvent("CHANGES_REQUESTED", PILOT_REASON_CODES[reason] ?? "OTHER");
      setChangesOpen(false);
      setReason("");
      setNote("");
      advanceMutation.mutate();
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.message : "Changes Requested failed");
    },
  });

  function handleApprove() {
    if (!isActionable || approveMutation.isPending) return;
    approveMutation.mutate();
  }

  function handleOpenChanges() {
    if (!isActionable) return;
    setReason("");
    setNote("");
    setChangesOpen(true);
  }

  function submitChangesRequested() {
    if (!reason) return;
    changesRequestedMutation.mutate();
  }

  function handleFlag() {
    setFlagNotice(
      "Flag is not implemented in HR-2 — no existing backend endpoint supports flagging an IN_REVIEW question " +
        "(content-reports is PUBLISHED-only). Reported as a gap; no mutation was sent.",
    );
    // Pilot evidence still records the flag decision itself (audit-log
    // only) even though there is no content-mutation endpoint to pair it
    // with — this is exactly the kind of gap HR-3 design needs visibility into.
    if (isActionable) sendPilotEvent("FLAGGED", "OTHER");
  }

  function handleSkip() {
    if (!isActionable || advanceMutation.isPending) return;
    setActionError(null);
    sendPilotEvent("SKIPPED");
    advanceMutation.mutate();
  }

  function goNext() {
    if (!session) return;
    setViewIndex((v) => Math.min(session.item_ids.length - 1, v + 1));
  }
  function goPrevious() {
    setViewIndex((v) => Math.max(0, v - 1));
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (isTypingTarget(document.activeElement)) return;
      if (e.key === "Escape") {
        if (changesOpen) setChangesOpen(false);
        return;
      }
      if (changesOpen) return; // don't fire review shortcuts while dialog is open
      const key = e.key.toLowerCase();
      if (key === "a") handleApprove();
      else if (key === "c") handleOpenChanges();
      else if (key === "f") handleFlag();
      else if (key === "s") handleSkip();
      else if (key === "n" || e.key === "ArrowRight") goNext();
      else if (key === "p" || e.key === "ArrowLeft") goPrevious();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [changesOpen, isActionable, currentViewedItemId, session]);

  const body = packet?.body as Record<string, unknown> | undefined;
  const ncertEvidence = (body?.ncert_evidence ?? null) as Record<string, unknown> | null;
  const options = useMemo(() => packet?.question?.options ?? [], [packet]);

  if (sessionQuery.isLoading) {
    return (
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4 px-4 py-6 sm:px-6">
        <Skeleton className="h-8 w-64" data-testid="session-loading" />
        <Skeleton className="h-96 w-full" />
      </main>
    );
  }

  if (sessionQuery.isError || !session) {
    return (
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4 px-4 py-6 sm:px-6">
        <Alert variant="destructive" data-testid="session-error">
          <AlertDescription>
            {sessionQuery.error instanceof ApiError ? sessionQuery.error.message : "Failed to load review session"}
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  if (session.status === "COMPLETED") {
    return (
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4 px-4 py-6 sm:px-6" data-testid="session-completed">
        <Card>
          <CardHeader>
            <CardTitle>Session complete</CardTitle>
            <CardDescription>
              Reviewed {session.item_ids.length} of {session.item_ids.length} questions in this session.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push("/admin/content/review-queue")}>Back to queue</Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  const reviewedCount = session.position;
  const remainingCount = session.remaining;

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-4 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Review Session</h1>
          <p className="text-sm text-muted-foreground" data-testid="session-progress">
            Question {viewIndex + 1} of {session.item_ids.length} · Reviewed {reviewedCount} · Remaining {remainingCount}
          </p>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" onClick={goPrevious} disabled={viewIndex === 0}>
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={goNext}
            disabled={viewIndex >= session.item_ids.length - 1}
          >
            Next
          </Button>
        </div>
      </div>

      {!isActionable ? (
        <Alert data-testid="readonly-preview-banner">
          <AlertDescription>
            Read-only preview — actions apply only to the current session item (position {session.position + 1}).
          </AlertDescription>
        </Alert>
      ) : null}

      {claimWarning ? (
        <Alert data-testid="claim-warning">
          <AlertDescription>{claimWarning}</AlertDescription>
        </Alert>
      ) : null}

      {flagNotice ? (
        <Alert data-testid="flag-notice">
          <AlertDescription>{flagNotice}</AlertDescription>
        </Alert>
      ) : null}

      {actionError ? (
        <Alert variant="destructive" data-testid="action-error">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      ) : null}

      {packetQuery.isLoading ? (
        <Skeleton className="h-96 w-full" data-testid="workspace-loading" />
      ) : packetQuery.isError ? (
        <Alert variant="destructive" data-testid="workspace-error">
          <AlertDescription>
            {packetQuery.error instanceof ApiError ? packetQuery.error.message : "Failed to load question"}
          </AlertDescription>
        </Alert>
      ) : packet ? (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{packet.academic?.subject?.name ?? "—"}</Badge>
              <Badge variant="outline">{packet.academic?.chapter?.name ?? "—"}</Badge>
              <Badge variant="outline">{packet.academic?.topic?.name ?? "—"}</Badge>
              <Badge variant="outline">{packet.academic?.concept?.name ?? "—"}</Badge>
              {packet.factory_qa?.blueprint_id ? (
                <Badge variant="outline">Blueprint {packet.factory_qa.blueprint_id.slice(0, 8)}</Badge>
              ) : null}
              {packet.provenance?.model_used ? <Badge variant="outline">{packet.provenance.model_used}</Badge> : null}
            </div>
            <CardTitle className="text-base" data-testid="question-stem">
              {packet.question?.stem}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <ul className="space-y-1" data-testid="question-options">
              {options.map((o) => (
                <li key={o.label}>
                  <strong>{o.label}.</strong> {o.text}
                  {packet.question?.correct_option === o.label ? " ✓" : ""}
                </li>
              ))}
            </ul>
            {packet.question?.explanation ? (
              <p className="text-muted-foreground" data-testid="question-explanation">
                {packet.question.explanation}
              </p>
            ) : null}

            <div className="rounded-md border p-3" data-testid="ncert-evidence">
              <p className="font-medium">NCERT evidence</p>
              {ncertEvidence ? (
                <dl className="mt-1 grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
                  <div>
                    <dt className="text-xs text-muted-foreground">Verification level</dt>
                    <dd>{String(ncertEvidence.verification_level ?? "—")}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Source document</dt>
                    <dd>{String(ncertEvidence.source_document ?? "—")}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted-foreground">Chapter / section</dt>
                    <dd>
                      {String(ncertEvidence.chapter ?? "—")} / {String(ncertEvidence.section ?? "—")}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-xs text-muted-foreground">No structured NCERT evidence persisted for this item.</p>
              )}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="sticky bottom-0 flex flex-wrap gap-2 border-t bg-background/95 py-3 backdrop-blur">
        <Button type="button" data-testid="action-approve" disabled={!isActionable || approveMutation.isPending} onClick={handleApprove}>
          Approve (A)
        </Button>
        <Button
          type="button"
          variant="secondary"
          data-testid="action-changes-requested"
          disabled={!isActionable}
          onClick={handleOpenChanges}
        >
          Changes Requested (C)
        </Button>
        <Button type="button" variant="outline" data-testid="action-flag" onClick={handleFlag}>
          Flag (F)
        </Button>
        <Button
          type="button"
          variant="ghost"
          data-testid="action-skip"
          disabled={!isActionable || advanceMutation.isPending}
          onClick={handleSkip}
        >
          Skip (S)
        </Button>
      </div>

      <Dialog open={changesOpen} onOpenChange={setChangesOpen}>
        <DialogContent aria-describedby="changes-requested-description">
          <DialogHeader>
            <DialogTitle>Changes Requested</DialogTitle>
            <DialogDescription id="changes-requested-description">
              Does not edit the question. A structured reason is required.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="changes-reason">Reason</Label>
              <select
                id="changes-reason"
                data-testid="changes-reason-select"
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              >
                <option value="">Select a reason…</option>
                {CHANGES_REQUESTED_REASONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="changes-note">Reviewer note (optional)</Label>
              <Textarea id="changes-note" data-testid="changes-note" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
            {changesRequestedMutation.isError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  {changesRequestedMutation.error instanceof ApiError
                    ? changesRequestedMutation.error.message
                    : "Changes Requested failed"}
                </AlertDescription>
              </Alert>
            ) : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setChangesOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              data-testid="submit-changes-requested"
              disabled={!reason || changesRequestedMutation.isPending}
              onClick={submitChangesRequested}
            >
              Submit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </main>
  );
}
