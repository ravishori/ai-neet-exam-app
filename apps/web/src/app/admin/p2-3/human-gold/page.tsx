"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, Upload } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cmsApi } from "@/features/cms/api";

type QueueItem = {
  question_id: string;
  source_question_id: string;
  subject: string;
  chapter: string;
  preaudit_priority: string;
  review_status: string;
  needs_attention?: boolean;
};

const FILTERS = ["all", "critical", "high", "medium", "low", "pending", "reviewed", "needs_attention"] as const;

function formatExpiry(seconds: number) {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  if (d > 1) return `${d} days ${h} hours remaining`;
  if (d === 1) return `24 hours remaining`;
  if (h > 0) return `${h} hours remaining`;
  return "Expires today";
}

export default function HumanGoldSandboxPage() {
  const qc = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [uploadPreview, setUploadPreview] = useState<Record<string, unknown> | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [sessionName, setSessionName] = useState("P2.3-R1 Gold Sample");
  const [filter, setFilter] = useState<string>("all");
  const [activeQ, setActiveQ] = useState<string | null>(null);
  const [humanForm, setHumanForm] = useState<Record<string, string>>({});

  const dashQuery = useQuery({
    queryKey: ["human-gold", "dashboard", sessionId],
    queryFn: () => cmsApi.humanGoldDashboard(sessionId!),
    enabled: Boolean(sessionId),
  });

  const queueQuery = useQuery({
    queryKey: ["human-gold", "queue", sessionId, filter],
    queryFn: async () => {
      const res = await cmsApi.humanGoldQueue(sessionId!, filter);
      return (res.items ?? []) as QueueItem[];
    },
    enabled: Boolean(sessionId),
  });

  const questionQuery = useQuery({
    queryKey: ["human-gold", "question", sessionId, activeQ],
    queryFn: () => cmsApi.humanGoldQuestion(sessionId!, activeQ!),
    enabled: Boolean(sessionId && activeQ),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => cmsApi.humanGoldUpload(file),
    onSuccess: (data) => {
      setUploadPreview((data.preview as Record<string, unknown>) ?? data);
      setUploadId(String(data.upload_id));
    },
  });

  const importMutation = useMutation({
    mutationFn: () => cmsApi.humanGoldImport({ upload_id: uploadId!, session_name: sessionName }),
    onSuccess: (data) => {
      setSessionId(String(data.session_id));
      setUploadPreview(null);
      qc.invalidateQueries({ queryKey: ["human-gold"] });
    },
  });

  const saveMutation = useMutation({
    mutationFn: ({ complete }: { complete: boolean }) =>
      cmsApi.humanGoldSave(sessionId!, activeQ!, { ...humanForm, mark_complete: complete }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["human-gold"] });
    },
  });

  const aiCheckMutation = useMutation({
    mutationFn: (batch: boolean) => cmsApi.humanGoldAiCheck(sessionId!, batch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["human-gold"] }),
  });

  const gateMutation = useMutation({
    mutationFn: () => cmsApi.humanGoldRunGate(sessionId!),
  });

  const packet = questionQuery.data as Record<string, unknown> | undefined;
  const original = (packet?.original ?? {}) as Record<string, unknown>;
  const opts = (original.options ?? {}) as Record<string, string>;
  const ai = (packet?.ai_assistance ?? {}) as Record<string, unknown>;
  const human = (packet?.human_gold ?? {}) as Record<string, unknown>;

  const queueItems = queueQuery.data ?? [];
  const activeIndex = useMemo(
    () => queueItems.findIndex((q) => q.question_id === activeQ),
    [queueItems, activeQ],
  );

  const loadHumanFromPacket = (p: Record<string, unknown>) => {
    const h = (p.human_gold ?? {}) as Record<string, string>;
    setHumanForm({
      human_stem: h.human_stem ?? "",
      human_option_A: h.human_option_A ?? "",
      human_option_B: h.human_option_B ?? "",
      human_option_C: h.human_option_C ?? "",
      human_option_D: h.human_option_D ?? "",
      human_answer: h.human_answer ?? "",
      human_explanation: h.human_explanation ?? "",
      human_ncert_support: h.human_ncert_support ?? "",
      human_ambiguity: h.human_ambiguity ?? "",
      human_duplicate: h.human_duplicate ?? "",
      human_difficulty: h.human_difficulty ?? "",
      human_neet_suitability: h.human_neet_suitability ?? "",
      human_overall: h.human_overall ?? "",
      reviewer_notes: h.reviewer_notes ?? "",
    });
  };

  useEffect(() => {
    if (questionQuery.data) loadHumanFromPacket(questionQuery.data as Record<string, unknown>);
  }, [questionQuery.data]);

  if (!sessionId) {
    return (
      <div className="mx-auto max-w-3xl space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold">P2.3 Human Gold Review Sandbox</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Isolated review environment. Human gold decisions are never copied from AI. Production MCQs are not modified.
          </p>
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="size-5" /> Upload P2.3 Gold Sample CSV
            </CardTitle>
            <CardDescription>UTF-8 CSV with required P2.3 columns (.csv only)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadMutation.mutate(f);
              }}
            />
            {uploadPreview && (
              <div className="space-y-3 rounded-md border p-4 text-sm">
                <p className="font-medium">P2.3 HUMAN GOLD SANDBOX — Preview</p>
                <p>Valid rows: {String((uploadPreview as Record<string, unknown>).valid_rows ?? "")}</p>
                <p>Invalid rows: {String((uploadPreview as Record<string, unknown>).invalid_rows ?? "")}</p>
                <p>
                  Pre-audit:{" "}
                  {(uploadPreview as Record<string, unknown>).preaudit_missing_note
                    ? String((uploadPreview as Record<string, unknown>).preaudit_missing_note)
                    : "Present"}
                </p>
                <Label>Session name</Label>
                <Input value={sessionName} onChange={(e) => setSessionName(e.target.value)} />
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setUploadPreview(null)}>
                    Cancel
                  </Button>
                  <Button disabled={!uploadId || importMutation.isPending} onClick={() => importMutation.mutate()}>
                    Import to Review Sandbox
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  const dash = dashQuery.data ?? {};

  return (
    <div className="grid min-h-screen grid-cols-1 gap-4 p-4 lg:grid-cols-[280px_1fr]">
      <aside className="space-y-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">P2.3 Human Gold Review</CardTitle>
            <CardDescription>{String(dash.session_name ?? "")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p>
              Progress: {String(dash.reviewed_count)}/{String(dash.question_count)} ({String(dash.progress_pct)}%)
            </p>
            <p>{formatExpiry(Number(dash.expires_in_seconds ?? 0))}</p>
            <div className="flex flex-wrap gap-1">
              <Badge>CRIT {String(dash.critical)}</Badge>
              <Badge variant="secondary">HIGH {String(dash.high)}</Badge>
              <Badge variant="outline">MED {String(dash.medium)}</Badge>
            </div>
            <Button size="sm" variant="outline" className="w-full" onClick={() => aiCheckMutation.mutate(true)}>
              Run AI Checks (All)
            </Button>
            <Button size="sm" variant="outline" className="w-full" onClick={() => gateMutation.mutate()}>
              Run Human-Gold Gate
            </Button>
          </CardContent>
        </Card>
        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <Button key={f} size="sm" variant={filter === f ? "default" : "ghost"} onClick={() => setFilter(f)}>
              {f}
            </Button>
          ))}
        </div>
        <div className="max-h-[60vh] space-y-1 overflow-y-auto">
          {queueItems.map((q) => (
            <button
              key={q.question_id}
              type="button"
              className={`w-full rounded border px-2 py-2 text-left text-xs ${activeQ === q.question_id ? "border-primary bg-muted" : ""}`}
              onClick={() => setActiveQ(q.question_id)}
            >
              <span className="font-mono">{q.source_question_id}</span>
              <div className="flex gap-1">
                <Badge variant="outline">{q.preaudit_priority}</Badge>
                {q.needs_attention && <Badge variant="destructive">!</Badge>}
              </div>
            </button>
          ))}
        </div>
      </aside>

      <main className="space-y-4">
        {!activeQ && (
          <EmptyState icon={ClipboardList} title="Select a question from the queue" description="Review CRITICAL items first." />
        )}
        {activeQ && packet && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {activeIndex + 1} / {queueItems.length} — {String(packet.subject)} → {String(packet.chapter)}
              </p>
              {(packet.flags as string[] | undefined)?.map((f) => (
                <Badge key={f} variant="destructive">
                  {f}
                </Badge>
              ))}
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">ORIGINAL AI DATA</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="whitespace-pre-wrap">{String(original.question ?? "")}</p>
                {(["A", "B", "C", "D"] as const).map((k) => (
                  <p key={k}>
                    {k}. {opts[k]}
                  </p>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">AI ASSISTANCE — NOT GOLD</CardTitle>
                <CardDescription>PRE-HUMAN AUDIT + deterministic checks</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-1 text-sm md:grid-cols-2">
                <p>Proposed: {String(original.proposed_answer)}</p>
                <p>Validator: {String(original.validator_verdict)}</p>
                <p>AI overall: {String(ai.ai_overall ?? "—")}</p>
                <p>NCERT: {String(ai.ai_ncert_support ?? "—")}</p>
                <p>Answer check: {String(ai.ai_answer_check ?? "—")}</p>
                <p>Provider: {String(ai.provider ?? "—")}</p>
                <Button size="sm" variant="outline" onClick={() => aiCheckMutation.mutate(false)}>
                  Run AI Check
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm">HUMAN GOLD DECISION</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(
                  [
                    ["human_stem", "Stem"],
                    ["human_option_A", "Option A"],
                    ["human_option_B", "Option B"],
                    ["human_option_C", "Option C"],
                    ["human_option_D", "Option D"],
                    ["human_answer", "Answer (A-D)"],
                    ["human_explanation", "Explanation"],
                    ["human_ncert_support", "NCERT support"],
                    ["human_ambiguity", "Ambiguity"],
                    ["human_duplicate", "Duplicate"],
                    ["human_difficulty", "Difficulty"],
                    ["human_neet_suitability", "NEET suitability"],
                    ["human_overall", "Overall"],
                    ["reviewer_notes", "Reviewer notes"],
                  ] as const
                ).map(([key, label]) =>
                  key === "human_explanation" || key === "reviewer_notes" ? (
                    <div key={key}>
                      <Label>{label}</Label>
                      <Textarea
                        value={humanForm[key] ?? ""}
                        onChange={(e) => setHumanForm((s) => ({ ...s, [key]: e.target.value }))}
                      />
                    </div>
                  ) : (
                    <div key={key}>
                      <Label>{label}</Label>
                      <Input
                        value={humanForm[key] ?? ""}
                        onChange={(e) => setHumanForm((s) => ({ ...s, [key]: e.target.value }))}
                      />
                    </div>
                  ),
                )}
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => saveMutation.mutate({ complete: false })}>
                    Save Draft
                  </Button>
                  <Button onClick={() => saveMutation.mutate({ complete: true })}>Save & Complete</Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      const prev = queueItems[activeIndex - 1];
                      if (prev) setActiveQ(prev.question_id);
                    }}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      const next = queueItems[activeIndex + 1];
                      if (next) setActiveQ(next.question_id);
                    }}
                  >
                    Next
                  </Button>
                </div>
                <p className="text-muted-foreground text-xs">Status: {String(human.review_status ?? "PENDING")}</p>
              </CardContent>
            </Card>

            {gateMutation.data && (
              <Alert>
                <AlertDescription>
                  Gate: {String((gateMutation.data as Record<string, unknown>).gate_status)} —{" "}
                  {String((gateMutation.data as Record<string, unknown>).gate_reason)}
                </AlertDescription>
              </Alert>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function EmptyState({
  icon: Icon,
  title,
  description,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
      <Icon className="text-muted-foreground mb-3 size-10" />
      <p className="font-medium">{title}</p>
      <p className="text-muted-foreground text-sm">{description}</p>
    </div>
  );
}
