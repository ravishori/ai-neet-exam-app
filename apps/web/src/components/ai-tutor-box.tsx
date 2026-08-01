"use client";

import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Send, Sparkles } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { MarkdownRenderer } from "@/components/markdown-renderer";
import { useTypewriter } from "@/hooks/use-typewriter";
import { ApiError } from "@/lib/api-client";
import { aiApi } from "@/features/ai/api";

const MAX_TEXTAREA_HEIGHT_PX = 160;

function AnswerSkeleton() {
  return (
    <div className="flex flex-col gap-3 px-(--card-spacing) py-4" aria-label="Loading answer" role="status">
      <Skeleton className="h-6 w-2/3" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="mt-2 h-24 w-full" />
      <span className="sr-only">Thinking…</span>
    </div>
  );
}

export function AiTutorBox({ conceptId }: { conceptId: string }) {
  const [question, setQuestion] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const ask = useMutation({ mutationFn: (q: string) => aiApi.tutorExplain({ concept_id: conceptId, question: q }) });
  const { displayedText, isTyping } = useTypewriter(ask.data?.answer ?? "");

  const submit = () => {
    const trimmed = question.trim();
    if (!trimmed || ask.isPending) return;
    ask.mutate(trimmed);
  };

  const autoGrow = (el: HTMLTextAreaElement) => {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT_PX)}px`;
  };

  return (
    <Card className="gap-0 overflow-hidden py-0">
      <CardHeader className="gap-1 border-b bg-muted/30 py-4">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" aria-hidden="true" />
          <CardTitle className="text-base">Ask the AI Tutor</CardTitle>
        </div>
        <CardDescription>Structured explanations, formulae, tips, and practice MCQs for this concept.</CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-0 px-0">
        <div className="sticky top-0 z-10 flex flex-col gap-1.5 border-b bg-card/95 px-(--card-spacing) py-3 backdrop-blur">
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              rows={1}
              value={question}
              onChange={(e) => {
                setQuestion(e.target.value);
                autoGrow(e.currentTarget);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder="Ask anything about this topic…"
              aria-label="Ask the AI Tutor a question"
              className="scroll-thin max-h-40 flex-1 resize-none rounded-2xl border bg-background px-4 py-2.5 text-sm leading-relaxed transition-shadow focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
            />
            <Button
              type="button"
              size="icon"
              className="rounded-full"
              disabled={!question.trim() || ask.isPending}
              onClick={submit}
              aria-label={ask.isPending ? "Asking the AI Tutor" : "Ask the AI Tutor"}
            >
              {ask.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Send className="size-4" aria-hidden="true" />}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            <kbd className="rounded border bg-muted px-1 py-0.5 font-sans">Enter</kbd> to ask ·{" "}
            <kbd className="rounded border bg-muted px-1 py-0.5 font-sans">Shift+Enter</kbd> for a new line
          </p>
        </div>

        {ask.isError && (
          <div className="px-(--card-spacing) pt-3">
            <Alert variant="destructive">
              <AlertDescription>{ask.error instanceof ApiError ? ask.error.message : "Something went wrong"}</AlertDescription>
            </Alert>
          </div>
        )}

        {ask.isPending && <AnswerSkeleton />}

        {ask.data && !ask.isPending && (
          <div className="flex flex-col gap-3 px-(--card-spacing) py-4">
            {ask.data.is_fallback && (
              <Badge variant="outline" className="w-fit">
                Fallback mode — no API key configured
              </Badge>
            )}
            <div className="scroll-thin max-h-[32rem] overflow-y-auto pr-1">
              <MarkdownRenderer content={displayedText} />
              {isTyping && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-foreground/60 align-middle" aria-hidden="true" />}
            </div>
            {ask.data.ncert_reference && (
              <p className="border-t pt-3 text-xs text-muted-foreground">NCERT reference: {ask.data.ncert_reference}</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
