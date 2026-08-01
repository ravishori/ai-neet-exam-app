"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
      aiApi.generateStudyPlan({ target_score: targetScore, current_score: currentScore, exam_date: examDate, hours_per_day: hoursPerDay }),
    onSuccess: (plan) => queryClient.setQueryData(["ai", "study-plan"], plan),
  });

  const plan = generate.data ?? existingPlan;

  return (
    <main className="flex flex-1 justify-center px-6 py-10">
      <div className="flex w-full max-w-xl flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>AI Study Planner</CardTitle>
            <CardDescription>Generates a plan from your target score, current score, and weak concepts.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {generate.isError && (
              <Alert variant="destructive">
                <AlertDescription>{generate.error instanceof ApiError ? generate.error.message : "Something went wrong"}</AlertDescription>
              </Alert>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label>Target score</Label>
                <Input type="number" value={targetScore} onChange={(e) => setTargetScore(Number(e.target.value))} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Current score</Label>
                <Input type="number" value={currentScore} onChange={(e) => setCurrentScore(Number(e.target.value))} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Exam date</Label>
                <Input type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Hours/day</Label>
                <Input type="number" value={hoursPerDay} onChange={(e) => setHoursPerDay(Number(e.target.value))} />
              </div>
            </div>
            <Button onClick={() => generate.mutate()} disabled={!examDate || generate.isPending} className="w-fit">
              {generate.isPending ? "Generating…" : "Generate plan"}
            </Button>
          </CardContent>
        </Card>

        {plan && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Your plan</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
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
                    <Badge variant="outline">{d.duration_minutes} min</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}
