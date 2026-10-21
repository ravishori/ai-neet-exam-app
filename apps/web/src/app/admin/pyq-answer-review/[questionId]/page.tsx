"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";
import { pyqAnswerReviewApi, type EvidenceSourceType } from "@/features/pyq-answer-review/api";

const OPTION_LABELS = ["A", "B", "C", "D"] as const;
const EVIDENCE_TYPES: EvidenceSourceType[] = ["OFFICIAL_ANSWER_KEY", "TEXTBOOK_REFERENCE", "EXPERT_REVIEW", "OTHER"];

export default function PyqAnswerReviewDetailPage() {
  const params = useParams<{ questionId: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const questionId = params.questionId;

  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [evidenceSourceType, setEvidenceSourceType] = useState<EvidenceSourceType>("OFFICIAL_ANSWER_KEY");
  const [evidenceLocator, setEvidenceLocator] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [sourceConsultedConfirmed, setSourceConsultedConfirmed] = useState(false);
  const [confirmStep, setConfirmStep] = useState(false);
  const [resultMessage, setResultMessage] = useState<string | null>(null);

  const detailQuery = useQuery({
    queryKey: ["pyq-answer-review", "detail", questionId],
    queryFn: () => pyqAnswerReviewApi.detail(questionId),
  });

  const saveMutation = useMutation({
    mutationFn: () => {
      const detail = detailQuery.data!;
      if (!selectedOption) throw new Error("Select an option first");
      return pyqAnswerReviewApi.save(questionId, {
        asserted_option: selectedOption,
        evidence_source_type: evidenceSourceType,
        evidence_locator: evidenceLocator || null,
        review_note: reviewNote || null,
        expected_state: detail.state,
        source_consulted_confirmed: sourceConsultedConfirmed,
      });
    },
    onSuccess: (result) => {
      setResultMessage(result.message);
      setConfirmStep(false);
      queryClient.invalidateQueries({ queryKey: ["pyq-answer-review"] });
      detailQuery.refetch();
    },
  });

  const skipMutation = useMutation({
    mutationFn: () => pyqAnswerReviewApi.skip(questionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pyq-answer-review"] });
      router.push("/admin/pyq-answer-review");
    },
  });

  if (detailQuery.isLoading) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-8">
        <Skeleton className="h-64 w-full" data-testid="detail-loading" />
      </main>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-8">
        <Alert variant="destructive" data-testid="detail-error">
          <AlertDescription>
            {detailQuery.error instanceof ApiError ? detailQuery.error.message : "Question failed to load"}
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  const detail = detailQuery.data;
  const verifiedAssertions = detail.existing_assertions.filter((a) => a.verification_status === "VERIFIED");
  const currentVerified = verifiedAssertions[verifiedAssertions.length - 1] ?? null;

  const canSubmit = Boolean(selectedOption) && sourceConsultedConfirmed;

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Review Question</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {detail.staging_id} · {detail.exam_year ?? "—"} · {detail.subject ?? "—"} · State: {detail.state}
        </p>
      </div>

      {currentVerified ? (
        <Alert data-testid="existing-verified-banner">
          <AlertDescription>
            A prior reviewer already recorded option <strong>{currentVerified.asserted_option}</strong> as
            verified ({currentVerified.evidence_source_type ?? "unknown source"}). Your selection below is a new,
            independent review — it will not silently overwrite that assertion.
          </AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Question</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="whitespace-pre-wrap text-sm">{detail.stem}</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {OPTION_LABELS.map((label) => {
              const isSelected = selectedOption === label;
              return (
                <button
                  key={label}
                  type="button"
                  data-testid={`option-${label}`}
                  onClick={() => setSelectedOption(label)}
                  className={`rounded-md border px-3 py-2 text-left text-sm transition ${
                    isSelected ? "border-primary bg-primary/10 font-medium" : "border-border hover:bg-muted/50"
                  }`}
                >
                  <span className="mr-2 font-semibold">{label}.</span>
                  {detail.options[label] ?? ""}
                </button>
              );
            })}
          </div>
          {selectedOption ? (
            <p className="text-xs text-muted-foreground" data-testid="selected-answer-label">
              Selected answer for this review: <strong>{selectedOption}</strong> (not yet saved)
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Evidence</CardTitle>
          <CardDescription>Required before saving — never fabricated.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {EVIDENCE_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                data-testid={`evidence-type-${type}`}
                onClick={() => setEvidenceSourceType(type)}
                className={`rounded-md border px-3 py-1.5 text-xs ${
                  evidenceSourceType === type ? "border-primary bg-primary/10 font-medium" : "border-border"
                }`}
              >
                {type.replaceAll("_", " ")}
              </button>
            ))}
          </div>
          <Input
            aria-label="Evidence locator"
            placeholder="Source locator (document name, page, question number, or URL)"
            value={evidenceLocator}
            onChange={(e) => setEvidenceLocator(e.target.value)}
          />
          <Input
            aria-label="Review note"
            placeholder="Optional review note"
            value={reviewNote}
            onChange={(e) => setReviewNote(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              data-testid="source-consulted-checkbox"
              checked={sourceConsultedConfirmed}
              onChange={(e) => setSourceConsultedConfirmed(e.target.checked)}
            />
            I confirm I checked this answer against the reference above before selecting it.
          </label>
        </CardContent>
      </Card>

      {resultMessage ? (
        <Alert data-testid="save-result">
          <AlertDescription>{resultMessage}</AlertDescription>
        </Alert>
      ) : null}
      {saveMutation.isError ? (
        <Alert variant="destructive" data-testid="save-error">
          <AlertDescription>
            {saveMutation.error instanceof ApiError ? saveMutation.error.message : "Save failed"}
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" onClick={() => router.push("/admin/pyq-answer-review")}>
          Back to queue
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={skipMutation.isPending}
          onClick={() => skipMutation.mutate()}
          data-testid="skip-button"
        >
          Skip for now
        </Button>
        {!confirmStep ? (
          <Button type="button" disabled={!canSubmit} onClick={() => setConfirmStep(true)} data-testid="review-save-button">
            Save answer
          </Button>
        ) : (
          <>
            <span className="text-sm">
              Confirm saving <strong>{selectedOption}</strong> as the verified answer?
            </span>
            <Button
              type="button"
              disabled={saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
              data-testid="confirm-save-button"
            >
              Yes, save
            </Button>
            <Button type="button" variant="outline" onClick={() => setConfirmStep(false)}>
              Cancel
            </Button>
          </>
        )}
      </div>
    </main>
  );
}
