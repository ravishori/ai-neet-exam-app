"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { MarkdownRenderer } from "@/components/markdown-renderer";
import { useTypewriter } from "@/hooks/use-typewriter";
import { ApiError } from "@/lib/api-client";
import { aiApi } from "@/features/ai/api";

function AnswerSkeleton() {
  return (
    <div className="flex flex-col gap-3 px-(--card-spacing) py-4" aria-label="Loading explanation" role="status">
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <span className="sr-only">Thinking…</span>
    </div>
  );
}

/** PR 8 — a focused "explain this specific question" action, distinct from
 * AiTutorBox's free-text concept chat. Only meant to be rendered where the
 * answer is already visible to the student (post-submit results/review) —
 * this never introduces a new way to see an answer without practicing. */
export function QuestionExplainCard({ questionId }: { questionId: string }) {
  const explain = useMutation({ mutationFn: () => aiApi.explainQuestion({ question_id: questionId }) });
  const { displayedText, isTyping } = useTypewriter(explain.data?.answer ?? "");

  return (
    <Card className="gap-0 overflow-hidden py-0">
      <CardHeader className="gap-1 border-b bg-muted/30 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" aria-hidden="true" />
            <CardTitle className="text-sm">AI Explanation</CardTitle>
          </div>
          {!explain.data && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={explain.isPending}
              onClick={() => explain.mutate()}
            >
              {explain.isPending ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> Explaining…
                </>
              ) : (
                "Explain this question"
              )}
            </Button>
          )}
        </div>
        {!explain.data && <CardDescription>Why the answer is right, why the others are wrong, and the concept behind it.</CardDescription>}
      </CardHeader>

      {(explain.isPending || explain.isError || explain.data) && (
        <CardContent className="flex flex-col gap-0 px-0">
          {explain.isError && (
            <div className="px-(--card-spacing) pt-3">
              <Alert variant="destructive">
                <AlertDescription>{explain.error instanceof ApiError ? explain.error.message : "Something went wrong"}</AlertDescription>
              </Alert>
            </div>
          )}

          {explain.isPending && <AnswerSkeleton />}

          {explain.data && !explain.isPending && (
            <div className="flex flex-col gap-3 px-(--card-spacing) py-4">
              {explain.data.is_fallback && (
                <Badge variant="outline" className="w-fit">
                  Fallback mode — no API key configured
                </Badge>
              )}
              <MarkdownRenderer content={displayedText} />
              {isTyping && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-foreground/60 align-middle" aria-hidden="true" />}
              {explain.data.ncert_reference && (
                <p className="border-t pt-3 text-xs text-muted-foreground">NCERT reference: {explain.data.ncert_reference}</p>
              )}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
