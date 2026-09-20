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
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { assessmentApi } from "@/features/assessment/api";
import { isNoQuestionsAvailable, thinContentMessage } from "@/features/assessment/thin-content";
import { MOCK_TEST_START_TEST_ID } from "@/features/assessment/use-start-practice";

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
    try {
      const assessment = await generate.mutateAsync();
      start.mutate(assessment.id);
    } catch {
      // Error surfaces through `generate.error` in the Alert below; the
      // rejection is swallowed here so it does not become an unhandled
      // promise rejection in the browser console.
    }
  };

  const pending = generate.isPending || start.isPending;
  const error = generate.error || start.error;

  return (
    <StudentPage width="md">
      <PageHeader
        eyebrow="Exam simulator"
        title="Mock test"
        description="Timed, NEET marking (+4 / −1). Uses every published question in scope — focused sets grow as more content is published."
      />

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
            <Alert variant="destructive" role="alert">
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
          <Button
            size="touch"
            onClick={onGenerate}
            disabled={pending}
            aria-busy={pending}
            data-testid={MOCK_TEST_START_TEST_ID}
            className="w-fit"
          >
            {pending ? "Starting…" : "Start mock test"}
          </Button>
          <p className="sr-only" aria-live="polite">
            {pending ? "Preparing your mock test" : error ? "Mock test start failed" : ""}
          </p>
        </SurfaceCardContent>
      </SurfaceCard>
    </StudentPage>
  );
}
