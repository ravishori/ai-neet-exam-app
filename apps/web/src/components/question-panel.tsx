"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Check, Flag, NotebookPen, Share2, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { MarkdownRenderer } from "@/components/markdown-renderer";
import { QuestionExplainCard } from "@/components/question-explain-card";
import type { AttemptQuestion, Confidence } from "@/features/assessment/api";
import { assessmentApi } from "@/features/assessment/api";
import { learningApi } from "@/features/learning/api";
import { questionsApi, type ReportReason } from "@/features/questions/api";
import { cn } from "@/lib/utils";

const CONFIDENCE_OPTIONS: { value: Confidence; label: string }[] = [
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
];

const REPORT_REASONS: { value: ReportReason; label: string }[] = [
  { value: "WRONG_ANSWER", label: "Answer looks wrong" },
  { value: "UNCLEAR", label: "Question is unclear" },
  { value: "TYPO", label: "Typo or formatting issue" },
  { value: "OFFENSIVE", label: "Offensive content" },
  { value: "OTHER", label: "Something else" },
];

function ZoomableImage({ src, alt }: { src: string; alt: string }) {
  return (
    <Dialog>
      <DialogTrigger
        render={
          <button
            type="button"
            className="group relative overflow-hidden rounded-md border border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          />
        }
      >
        <img src={src} alt={alt} className="h-auto max-h-64 w-auto max-w-full object-contain" />
        <span className="absolute inset-0 flex items-center justify-center bg-black/0 text-xs font-medium text-transparent transition-colors group-hover:bg-black/30 group-hover:text-white">
          Click to zoom
        </span>
      </DialogTrigger>
      <DialogContent className="sm:max-w-3xl" showCloseButton>
        <img src={src} alt={alt} className="h-auto max-h-[80vh] w-full object-contain" />
      </DialogContent>
    </Dialog>
  );
}

function DifficultyBadge({ difficulty }: { difficulty?: string }) {
  if (!difficulty) return null;
  return (
    <Badge variant={difficulty === "hard" ? "destructive" : difficulty === "easy" ? "secondary" : "outline"}>{difficulty}</Badge>
  );
}

function PreviousAttempts({ contentItemId }: { contentItemId: string }) {
  const query = useQuery({
    queryKey: ["question-history", contentItemId],
    queryFn: () => assessmentApi.questionHistory(contentItemId),
  });

  return (
    <Dialog>
      <DialogTrigger render={<Button type="button" variant="outline" size="sm" />}>Previous attempts</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Previous attempts</DialogTitle>
          <DialogDescription>Every past submitted answer you&apos;ve given for this question.</DialogDescription>
        </DialogHeader>
        {query.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {query.data && query.data.length === 0 && (
          <p className="text-sm text-muted-foreground">You haven&apos;t answered this question in a submitted attempt before.</p>
        )}
        {query.data && query.data.length > 0 && (
          <ul className="flex flex-col gap-2 text-sm">
            {query.data.map((entry, idx) => (
              <li key={idx} className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2">
                <span className={entry.is_correct ? "text-green-700 dark:text-green-400" : "text-destructive"}>
                  {entry.selected_option ? `Selected ${entry.selected_option}` : "Skipped"} — {entry.is_correct ? "Correct" : "Incorrect"}
                </span>
                <span className="text-xs text-muted-foreground">{new Date(entry.answered_at).toLocaleDateString()}</span>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}

function RelatedQuestions({ contentItemId }: { contentItemId: string }) {
  const query = useQuery({
    queryKey: ["question-related", contentItemId],
    queryFn: () => questionsApi.related(contentItemId),
  });

  if (!query.data || query.data.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-medium text-foreground">Related questions</h3>
      <ul className="flex flex-col gap-2">
        {query.data.map((q) => (
          <li key={q.id}>
            <a
              href={`/student/questions/${q.id}`}
              target="_blank"
              rel="noreferrer"
              className="block rounded-md border border-border px-3 py-2 text-sm text-foreground underline-offset-2 hover:underline"
            >
              {q.stem}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function QuestionPanel({
  question,
  index,
  total,
  isSubmitted,
  onSelectOption,
  onSetConfidence,
  onToggleMarkForReview,
}: {
  question: AttemptQuestion;
  index: number;
  total: number;
  isSubmitted: boolean;
  onSelectOption: (label: string) => void;
  onSetConfidence: (confidence: Confidence) => void;
  onToggleMarkForReview: () => void;
}) {
  const queryClient = useQueryClient();
  const [noteText, setNoteText] = useState("");
  const [noteDialogOpen, setNoteDialogOpen] = useState(false);
  const [reportReason, setReportReason] = useState<ReportReason>("UNCLEAR");
  const [reportComment, setReportComment] = useState("");
  const [reportSubmitted, setReportSubmitted] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  const noteQuery = useQuery({
    queryKey: ["question-note", question.content_item_id],
    queryFn: () => learningApi.getNote(question.content_item_id),
    enabled: noteDialogOpen,
  });

  const bookmarkToggle = useMutation({
    mutationFn: () => learningApi.toggleBookmark(question.content_item_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["assessment", "attempt"] }),
  });

  const noteSave = useMutation({
    mutationFn: (text: string) => learningApi.upsertNote(question.content_item_id, text),
    onSuccess: () => setNoteDialogOpen(false),
  });

  const reportSubmit = useMutation({
    mutationFn: () => questionsApi.report(question.content_item_id, { reason: reportReason, comment: reportComment || undefined }),
    onSuccess: () => setReportSubmitted(true),
  });

  async function handleShare() {
    const url = `${window.location.origin}/student/questions/${question.content_item_id}`;
    try {
      await navigator.clipboard.writeText(url);
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2000);
    } catch {
      // Clipboard API unavailable — nothing to fall back to without a backend share link.
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-muted-foreground">
          Question {index + 1} of {total}
        </span>
        <div className="flex flex-wrap items-center gap-1.5">
          <DifficultyBadge difficulty={question.difficulty} />
          <Badge variant="outline">{question.question_type}</Badge>
          {question.pyq_year && <Badge variant="ghost">PYQ {question.pyq_year}</Badge>}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5" aria-label="Question metadata">
        {question.subject && <Badge variant="outline">{question.subject.name}</Badge>}
        {question.chapter && <Badge variant="outline">{question.chapter.name}</Badge>}
        {question.topic && <Badge variant="outline">{question.topic.name}</Badge>}
        {question.concept && <Badge variant="outline">{question.concept.name}</Badge>}
      </div>

      <div className="text-lg leading-relaxed font-medium text-foreground">
        <MarkdownRenderer content={question.stem} />
      </div>

      {question.images.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {question.images.map((img) => (
            <ZoomableImage key={img.id} src={`/api/visual-assets/${img.id}`} alt={img.alt_text ?? "Diagram accompanying this question"} />
          ))}
        </div>
      )}

      <fieldset className="flex flex-col gap-2" disabled={isSubmitted}>
        <legend className="sr-only">Answer options</legend>
        {question.options.map((opt, optIdx) => {
          const isSelected = question.selected_option === opt.label;
          const isCorrectOpt = isSubmitted && question.correct_option === opt.label;
          const isWrongSelected = isSubmitted && isSelected && !isCorrectOpt;
          return (
            <button
              key={opt.label}
              type="button"
              disabled={isSubmitted}
              onClick={() => onSelectOption(opt.label)}
              className={cn(
                "flex items-start gap-3 rounded-lg border p-3 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-default",
                isCorrectOpt && "border-green-600 bg-green-50 dark:border-green-500 dark:bg-green-950",
                isWrongSelected && "border-destructive bg-destructive/10",
                !isSubmitted && isSelected && "border-primary bg-primary/5",
                !isSubmitted && !isSelected && "border-border hover:border-primary/50 hover:bg-muted/50"
              )}
            >
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold tabular-nums",
                  isSelected || isCorrectOpt ? "border-current" : "border-muted-foreground/40 text-muted-foreground"
                )}
                aria-hidden="true"
              >
                {optIdx < 4 ? String.fromCharCode(65 + optIdx) : opt.label}
              </span>
              <span className="pt-0.5">{opt.text}</span>
              {isCorrectOpt && <Check className="ml-auto size-4 shrink-0 text-green-600 dark:text-green-400" aria-hidden="true" />}
              {isWrongSelected && <X className="ml-auto size-4 shrink-0 text-destructive" aria-hidden="true" />}
            </button>
          );
        })}
      </fieldset>
      <p className="text-xs text-muted-foreground">Keyboard shortcuts: A, B, C, D select an option.</p>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant={question.bookmarked ? "default" : "outline"}
          size="sm"
          onClick={() => bookmarkToggle.mutate()}
          disabled={bookmarkToggle.isPending}
        >
          <Bookmark className="size-3.5" aria-hidden="true" />
          {question.bookmarked ? "Bookmarked" : "Bookmark"}
        </Button>

        <Dialog open={noteDialogOpen} onOpenChange={(open) => {
          setNoteDialogOpen(open);
          if (open) setNoteText(noteQuery.data?.note_text ?? "");
        }}>
          <DialogTrigger render={<Button type="button" variant="outline" size="sm" />}>
            <NotebookPen className="size-3.5" aria-hidden="true" /> Note
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Your note</DialogTitle>
              <DialogDescription>Personal notes are only visible to you.</DialogDescription>
            </DialogHeader>
            <Textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Write a note for this question…"
              rows={5}
            />
            <DialogFooter>
              <Button type="button" onClick={() => noteSave.mutate(noteText)} disabled={noteSave.isPending}>
                {noteSave.isPending ? "Saving…" : "Save note"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Button type="button" variant="outline" size="sm" onClick={handleShare}>
          <Share2 className="size-3.5" aria-hidden="true" /> {shareCopied ? "Link copied" : "Share"}
        </Button>

        <PreviousAttempts contentItemId={question.content_item_id} />

        <Dialog onOpenChange={(open) => {
          if (!open) {
            setReportSubmitted(false);
            setReportComment("");
          }
        }}>
          <DialogTrigger render={<Button type="button" variant="ghost" size="sm" />}>
            <Flag className="size-3.5" aria-hidden="true" /> Report issue
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Report an issue</DialogTitle>
              <DialogDescription>Flag a problem with this question for the content team to review.</DialogDescription>
            </DialogHeader>
            {reportSubmitted ? (
              <p className="text-sm text-green-700 dark:text-green-400">Thanks — your report has been submitted.</p>
            ) : (
              <>
                <div className="flex flex-col gap-1.5">
                  {REPORT_REASONS.map((r) => (
                    <label key={r.value} className="flex items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="report-reason"
                        checked={reportReason === r.value}
                        onChange={() => setReportReason(r.value)}
                      />
                      {r.label}
                    </label>
                  ))}
                </div>
                <Textarea
                  value={reportComment}
                  onChange={(e) => setReportComment(e.target.value)}
                  placeholder="Optional details…"
                  rows={3}
                />
                <DialogFooter>
                  <Button type="button" onClick={() => reportSubmit.mutate()} disabled={reportSubmit.isPending}>
                    {reportSubmit.isPending ? "Submitting…" : "Submit report"}
                  </Button>
                </DialogFooter>
              </>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {!isSubmitted && (
        <div className="flex flex-wrap items-center gap-2 border-t pt-3">
          <span className="text-xs font-medium text-muted-foreground">How confident are you?</span>
          {CONFIDENCE_OPTIONS.map((c) => (
            <Button
              key={c.value}
              type="button"
              size="sm"
              variant={question.confidence === c.value ? "default" : "outline"}
              onClick={() => onSetConfidence(c.value)}
            >
              {c.label}
            </Button>
          ))}
          <Button
            type="button"
            size="sm"
            variant={question.marked_for_review ? "default" : "outline"}
            className="ml-auto"
            onClick={onToggleMarkForReview}
          >
            {question.marked_for_review ? "Marked for review" : "Mark for review"}
          </Button>
        </div>
      )}

      {isSubmitted && (
        <div className="flex flex-col gap-4 border-t pt-4">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Badge variant={question.is_correct ? "secondary" : "destructive"}>
              {question.is_correct === null ? "Skipped" : question.is_correct ? "Correct" : "Incorrect"}
            </Badge>
            {question.confidence && <Badge variant="outline">Confidence: {question.confidence}</Badge>}
            {typeof question.time_spent_seconds === "number" && (
              <span className="text-muted-foreground">Time spent: {question.time_spent_seconds}s</span>
            )}
          </div>

          {question.explanation && (
            <div className="rounded-md border border-border bg-muted/30 p-3">
              <h3 className="mb-1 text-sm font-medium text-foreground">Explanation</h3>
              <MarkdownRenderer content={question.explanation} />
            </div>
          )}

          {question.ncert_reference && (
            <p className="text-xs text-muted-foreground">NCERT reference: {question.ncert_reference}</p>
          )}

          <QuestionExplainCard questionId={question.content_item_id} />

          <RelatedQuestions contentItemId={question.content_item_id} />
        </div>
      )}
    </div>
  );
}
