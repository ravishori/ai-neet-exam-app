"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { ApiError } from "@/lib/api-client";
import { aiApi } from "@/features/ai/api";

export default function StudyPlanPage() {
  const queryClient = useQueryClient();
  const [targetScore, setTargetScore] = useState(650);
  const [currentScore, setCurrentScore] = useState(450);
  const [examDate, setExamDate] = useState("");
  const [hoursPerDay, setHoursPerDay] = useState(6);

  const { data: existingPlan } = useQuery({
    queryKey: ["ai", "study-plan"],
    queryFn: aiApi.getStudyPlan,
    retry: false,
  });

  const generate = useMutation({
    mutationFn: () =>
      aiApi.generateStudyPlan({
        target_score: targetScore,
        current_score: currentScore,
        exam_date: examDate,
        hours_per_day: hoursPerDay,
      }),
    onSuccess: (plan) => queryClient.setQueryData(["ai", "study-plan"], plan),
  });

  const plan = generate.data ?? existingPlan;

  return (
    <main className="mx-auto flex w-full max-w-xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6 animate-fade-slide-up">
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.14em]" style={{ color: "var(--ai-from)" }}>
          AI Study Coach
        </p>
        <h1 className="font-heading text-3xl font-bold tracking-tight">Study plan</h1>
        <p className="text-sm text-muted-foreground">
          Generates a plan from your target score, current score, and weak concepts.
        </p>
      </div>

      <SurfaceCard accent="none" className="overflow-hidden">
        <div className="h-1 w-full ai-gradient" aria-hidden />
        <SurfaceCardHeader>
          <div className="flex items-center gap-2">
            <span className="flex size-9 items-center justify-center rounded-xl ai-gradient text-white">
              <Sparkles className="size-4" aria-hidden />
            </span>
            <div>
              <SurfaceCardTitle>Planner inputs</SurfaceCardTitle>
              <SurfaceCardDescription>Same study-plan API — restyled coach surface.</SurfaceCardDescription>
            </div>
          </div>
        </SurfaceCardHeader>
        <SurfaceCardContent className="flex flex-col gap-4">
          {generate.isError && (
            <Alert variant="destructive">
              <AlertDescription>
                {generate.error instanceof ApiError ? generate.error.message : "Something went wrong"}
              </AlertDescription>
            </Alert>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label>Target score</Label>
              <Input
                type="number"
                value={targetScore}
                onChange={(e) => setTargetScore(Number(e.target.value))}
                className="font-mono tabular-nums"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Current score</Label>
              <Input
                type="number"
                value={currentScore}
                onChange={(e) => setCurrentScore(Number(e.target.value))}
                className="font-mono tabular-nums"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Exam date</Label>
              <Input type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Hours/day</Label>
              <Input
                type="number"
                value={hoursPerDay}
                onChange={(e) => setHoursPerDay(Number(e.target.value))}
                className="font-mono tabular-nums"
              />
            </div>
          </div>
          <Button onClick={() => generate.mutate()} disabled={!examDate || generate.isPending} className="w-fit">
            {generate.isPending ? "Generating…" : "Generate plan"}
          </Button>
        </SurfaceCardContent>
      </SurfaceCard>

      {plan && (
        <SurfaceCard accent="none">
          <SurfaceCardHeader>
            <SurfaceCardTitle>Your plan</SurfaceCardTitle>
          </SurfaceCardHeader>
          <SurfaceCardContent className="flex flex-col gap-3">
            <p className="text-sm">{plan.plan.summary}</p>
            <div>
              <p className="text-sm font-medium">Weekly focus</p>
              <ul className="list-inside list-disc text-sm text-muted-foreground">
                {plan.plan.weekly_focus.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
            </div>
            <div className="flex flex-col gap-1">
              {plan.plan.daily_schedule.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span>
                    Day {d.day}: {d.focus}
                  </span>
                  <Badge variant="outline" className="font-mono tabular-nums">
                    {d.duration_minutes} min
                  </Badge>
                </div>
              ))}
            </div>
          </SurfaceCardContent>
        </SurfaceCard>
      )}
    </main>
  );
}
