"use client";

import Link from "next/link";
import { useState } from "react";
import { Loader2, Target } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ScopePicker, type Scope } from "@/components/scope-picker";
import {
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { isNoQuestionsAvailable } from "@/features/assessment/thin-content";
import { practiceStartMessage, useStartPractice } from "@/features/assessment/use-start-practice";

export default function PracticePage() {
  const [scope, setScope] = useState<Scope | null>(null);
  const start = useStartPractice();

  const onGenerate = () => {
    start.mutate(
      scope
        ? { scope_type: scope.scope_type, scope_id: scope.scope_id, question_count: 30 }
        : { scope_type: "FULL", question_count: 30 },
    );
  };

  const emptyPool = start.isError && isNoQuestionsAvailable(start.error);

  return (
    <StudentPage width="md">
      <PageHeader
        eyebrow="Practice arena"
        title="Adaptive practice"
        description="Untimed drills with no negative marking. Scope to a subject, chapter, topic, or concept — or leave open for any published question."
      />

      <SurfaceCard theme="physics" accent="top">
        <SurfaceCardHeader>
          <div className="flex items-center gap-2">
            <span className="flex size-9 items-center justify-center rounded-xl bg-subject-physics-muted text-subject-physics">
              <Target className="size-4" aria-hidden />
            </span>
            <div>
              <SurfaceCardTitle>Configure session</SurfaceCardTitle>
              <SurfaceCardDescription>Published questions only — drafts never appear here.</SurfaceCardDescription>
            </div>
          </div>
        </SurfaceCardHeader>
        <SurfaceCardContent className="flex flex-col gap-4">
          {emptyPool && (
            <Alert role="status">
              <AlertDescription className="space-y-2">
                <p className="font-medium">Practice is not available for this selection yet.</p>
                <p>{practiceStartMessage(start.error)}</p>
                <p className="text-sm text-muted-foreground">
                  No published questions are currently available for this scope. Try another topic, chapter, or start
                  with any published question.
                </p>
                <div className="flex flex-wrap gap-3 text-sm">
                  <button type="button" className="underline-offset-2 hover:underline" onClick={onGenerate}>
                    Retry
                  </button>
                  <button
                    type="button"
                    className="underline-offset-2 hover:underline"
                    onClick={() => start.mutate({ scope_type: "FULL", question_count: 30 })}
                  >
                    Practice any published question
                  </button>
                  <Link href="/student/subjects" className="underline-offset-2 hover:underline">
                    Browse subjects
                  </Link>
                  <Link href="/student/dashboard" className="underline-offset-2 hover:underline">
                    Return to dashboard
                  </Link>
                </div>
              </AlertDescription>
            </Alert>
          )}
          {start.isError && !emptyPool && (
            <Alert variant="destructive" role="alert">
              <AlertDescription className="space-y-2">
                <p>{practiceStartMessage(start.error)}</p>
                <button type="button" className="text-sm underline-offset-2 hover:underline" onClick={onGenerate}>
                  Retry
                </button>
              </AlertDescription>
            </Alert>
          )}
          <ScopePicker onChange={setScope} />
          <p className="text-sm text-muted-foreground">
            Scope: {scope ? `${scope.scope_type.toLowerCase()} — ${scope.label}` : "any published question"}
          </p>
          <Button
            type="button"
            onClick={onGenerate}
            disabled={start.isPending}
            aria-busy={start.isPending}
            className="min-h-12 w-full touch-manipulation sm:w-fit"
          >
            {start.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Preparing your practice session…
              </>
            ) : (
              "Enter practice arena"
            )}
          </Button>
          <p className="sr-only" aria-live="polite">
            {start.isPending
              ? "Preparing your practice session"
              : emptyPool
                ? "No published questions for this selection"
                : ""}
          </p>
        </SurfaceCardContent>
      </SurfaceCard>
    </StudentPage>
  );
}
