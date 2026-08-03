"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MasteryBar } from "@/components/mastery-badge";
import { ScoreTrendChart } from "@/components/score-trend-chart";
import { cn } from "@/lib/utils";
import { useMe } from "@/features/auth/use-auth";
import { assessmentApi } from "@/features/assessment/api";
import { computeScoreTrend } from "@/features/assessment/analytics";
import { learningApi, type RecommendationReason } from "@/features/learning/api";

const REASON_LABEL: Record<RecommendationReason, string> = {
  due_for_revision: "Due for revision",
  weak_concept: "Needs practice",
  new_concept: "Not started yet",
};

function PracticeNowButton({ conceptId }: { conceptId: string }) {
  const router = useRouter();
  const start = useMutation({
    mutationFn: async () => {
      const assessment = await assessmentApi.generatePractice({ scope_type: "CONCEPT", scope_id: conceptId });
      return assessmentApi.startAttempt(assessment.id);
    },
    onSuccess: (attempt) => router.push(`/student/attempts/${attempt.id}`),
  });

  return (
    <Button size="sm" variant="outline" disabled={start.isPending} onClick={() => start.mutate()}>
      {start.isPending ? "Starting…" : "Practice now"}
    </Button>
  );
}

export default function StudentDashboardPage() {
  const { data: user, isLoading } = useMe();
  const { data: overview } = useQuery({ queryKey: ["learning", "overview"], queryFn: learningApi.overview });
  const { data: revisionDue } = useQuery({ queryKey: ["learning", "revision-due"], queryFn: learningApi.revisionDue });
  const { data: recommendations } = useQuery({ queryKey: ["learning", "recommendations"], queryFn: learningApi.recommendations });
  const { data: attempts } = useQuery({ queryKey: ["assessment", "attempts"], queryFn: assessmentApi.listAttempts });
  const scoreTrend = attempts ? computeScoreTrend(attempts) : [];

  return (
    <main className="flex flex-1 flex-col items-center gap-6 px-6 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">
          {isLoading ? "Loading…" : `Welcome, ${user?.first_name ?? user?.email}`}
        </h1>
      </div>

      <Link href="/student/subjects" className={cn(buttonVariants())}>
        Browse subjects
      </Link>

      {revisionDue && revisionDue.length > 0 && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-base">Revision queue</CardTitle>
            <CardDescription>Concepts due for another look.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {revisionDue.map((item) => (
              <div key={item.concept_id} className="flex items-center justify-between gap-2">
                <span className="text-sm">{item.concept_name}</span>
                <PracticeNowButton conceptId={item.concept_id} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {recommendations && recommendations.length > 0 && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-base">Recommended practice</CardTitle>
            <CardDescription>What to work on next.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {recommendations.map((item) => (
              <div key={item.concept_id} className="flex items-center justify-between gap-2">
                <div className="flex flex-col">
                  <span className="text-sm">{item.concept_name}</span>
                  <span className="text-xs text-muted-foreground">{REASON_LABEL[item.reason]}</span>
                </div>
                <PracticeNowButton conceptId={item.concept_id} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {overview && overview.length > 0 && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-base">Mastery by subject</CardTitle>
            <CardDescription>Based on your practice and mock test attempts.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {overview.map((s) => (
              <div key={s.subject_id} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{s.subject_name}</span>
                  <span className="text-muted-foreground">
                    {s.concepts_attempted}/{s.concepts_total} concepts · {s.average_score}%
                  </span>
                </div>
                <MasteryBar score={s.average_score} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {attempts && attempts.some((a) => a.status === "SUBMITTED") && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-base">Accuracy trend</CardTitle>
            <CardDescription>
              <Link href="/student/attempts" className="hover:underline">
                Your last {scoreTrend.length} submitted attempts
              </Link>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScoreTrendChart points={scoreTrend} />
          </CardContent>
        </Card>
      )}

      {user && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-base">Account</CardTitle>
            <CardDescription>{user.email}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {user.roles.map((role) => (
              <Badge key={role} variant="secondary">
                {role}
              </Badge>
            ))}
            {!user.email_verified && <Badge variant="outline">Email not verified</Badge>}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
