"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScopePicker, type Scope } from "@/components/scope-picker";
import { ApiError } from "@/lib/api-client";
import { assessmentApi } from "@/features/assessment/api";

export default function PracticePage() {
  const router = useRouter();
  const [scope, setScope] = useState<Scope | null>(null);

  const generate = useMutation({
    mutationFn: () =>
      assessmentApi.generatePractice(
        scope ? { scope_type: scope.scope_type, scope_id: scope.scope_id } : { scope_type: "FULL" }
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

  return (
    <main className="flex flex-1 justify-center px-6 py-10">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>Practice</CardTitle>
          <CardDescription>Untimed, no negative marking — pick a scope or leave it open for anything published.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {(generate.isError || start.isError) && (
            <Alert variant="destructive">
              <AlertDescription>
                {generate.error instanceof ApiError
                  ? generate.error.message
                  : start.error instanceof ApiError
                    ? start.error.message
                    : "Something went wrong"}
              </AlertDescription>
            </Alert>
          )}
          <ScopePicker onChange={setScope} />
          <p className="text-sm text-muted-foreground">
            Scope: {scope ? `${scope.scope_type.toLowerCase()} — ${scope.label}` : "any published question"}
          </p>
          <Button onClick={onGenerate} disabled={generate.isPending || start.isPending} className="w-fit">
            {generate.isPending || start.isPending ? "Starting…" : "Start practice"}
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
