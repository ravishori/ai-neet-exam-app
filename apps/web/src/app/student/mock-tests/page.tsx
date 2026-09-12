"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ScopePicker, type Scope } from "@/components/scope-picker";
import {
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { assessmentApi } from "@/features/assessment/api";
import { isNoQuestionsAvailable, thinContentMessage } from "@/features/assessment/thin-content";

export default function MockTestsPage() {
  const router = useRouter();
  const [scope, setScope] = useState<Scope | null>(null);

  const generate = useMutation({
    mutationFn: () =>
      assessmentApi.generateMock(
        scope ? { scope_type: scope.scope_type, scope_id: scope.scope_id } : { scope_type: "FULL" },
      ),
  });
  const start = useMutation({
    mutationFn: (assessmentId: string) => assessmentApi.startAttempt(assessmentId),
    onSuccess: (attempt) => router.push(`/student/attempts/${attempt.id}`),
  });

  const onGenerate = async () => {
    const assessment = await generate.mutateAsync();
    start.mutate(assessment.id);
  };

  const error = generate.error || start.error;

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6 animate-fade-slide-up">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-subject-chemistry">Exam simulator</p>
        <h1 className="font-heading text-3xl font-bold tracking-tight">Mock test</h1>
        <p className="text-sm text-muted-foreground">
          Timed, NEET marking (+4 / −1). Uses every published question in scope — with the current library that is a
          focused set, not a full 180-question paper. More ECAEP content grows the mock naturally.
        </p>
      </div>

      <SurfaceCard theme="chemistry" accent="top">
        <SurfaceCardHeader>
          <div className="flex items-center gap-2">
            <span className="flex size-9 items-center justify-center rounded-xl bg-subject-chemistry-muted text-subject-chemistry">
              <ClipboardList className="size-4" aria-hidden />
            </span>
            <div>
              <SurfaceCardTitle>Launch exam mode</SurfaceCardTitle>
              <SurfaceCardDescription>
                Decorative motion is suppressed once the timer starts — focus stays on the paper.
              </SurfaceCardDescription>
            </div>
          </div>
        </SurfaceCardHeader>
        <SurfaceCardContent className="flex flex-col gap-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription className="space-y-2">
                <p>{thinContentMessage(error)}</p>
                {isNoQuestionsAvailable(error) && (
                  <div className="flex flex-wrap gap-3 text-sm">
                    <Link href="/student/practice" className="underline-offset-2 hover:underline">
                      Try practice instead
                    </Link>
                    <Link href="/student/subjects" className="underline-offset-2 hover:underline">
                      Try another subject
                    </Link>
                    <Link href="/student/dashboard" className="underline-offset-2 hover:underline">
                      Return to dashboard
                    </Link>
                  </div>
                )}
              </AlertDescription>
            </Alert>
          )}
          <ScopePicker onChange={setScope} />
          <p className="text-sm text-muted-foreground">
            Scope: {scope ? `${scope.scope_type.toLowerCase()} — ${scope.label}` : "full syllabus"}
          </p>
          <Button onClick={onGenerate} disabled={generate.isPending || start.isPending} className="w-fit">
            {generate.isPending || start.isPending ? "Starting…" : "Start mock test"}
          </Button>
        </SurfaceCardContent>
      </SurfaceCard>
    </main>
  );
}
