"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { analyticsApi } from "@/features/analytics/api";

function TrendChart({ points }: { points: { date: string; attempts: number }[] }) {
  const max = Math.max(1, ...points.map((p) => p.attempts));
  return (
    <div className="flex h-24 items-end gap-1">
      {points.map((p) => (
        <div key={p.date} className="flex flex-1 flex-col items-center gap-1" title={`${p.date}: ${p.attempts}`}>
          <div
            className="w-full rounded-t bg-primary transition-all"
            style={{ height: `${(p.attempts / max) * 100}%`, minHeight: p.attempts > 0 ? "2px" : 0 }}
          />
        </div>
      ))}
    </div>
  );
}

export default function AdminAnalyticsPage() {
  const { data: assessmentStats, isLoading: loadingAssessments } = useQuery({
    queryKey: ["analytics", "assessments"],
    queryFn: analyticsApi.assessments,
  });
  const { data: aiUsage, isLoading: loadingAi } = useQuery({
    queryKey: ["analytics", "ai-usage"],
    queryFn: analyticsApi.aiUsage,
  });

  if (loadingAssessments || loadingAi) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 px-6 py-10">
      <h1 className="mb-6 text-xl font-semibold">Analytics</h1>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Assessment overview</CardTitle>
            <CardDescription>{assessmentStats?.total_attempts ?? 0} submitted attempts across the platform.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-semibold">{assessmentStats?.average_score_percent ?? 0}%</span>
              <span className="text-sm text-muted-foreground">average score</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {assessmentStats?.by_type.map((t) => (
                <Badge key={t.assessment_type} variant="outline">
                  {t.assessment_type}: {t.attempts} attempts · {t.average_score_percent}%
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Attempts, last 14 days</CardTitle>
            <CardDescription>Daily submitted-attempt volume.</CardDescription>
          </CardHeader>
          <CardContent>
            {assessmentStats && <TrendChart points={assessmentStats.attempts_trend} />}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Weakest concepts</CardTitle>
            <CardDescription>Lowest accuracy platform-wide (min. 3 attempts).</CardDescription>
          </CardHeader>
          <CardContent>
            {assessmentStats && assessmentStats.weakest_concepts.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th className="p-1.5 font-normal">Concept</th>
                      <th className="p-1.5 font-normal">Subject</th>
                      <th className="p-1.5 text-right font-normal">Attempts</th>
                      <th className="p-1.5 text-right font-normal">Accuracy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assessmentStats.weakest_concepts.map((c) => (
                      <tr key={c.concept_id} className="border-t">
                        <td className="p-1.5">{c.concept_name}</td>
                        <td className="p-1.5 text-muted-foreground">{c.subject_name}</td>
                        <td className="p-1.5 text-right tabular-nums">{c.attempts}</td>
                        <td className="p-1.5 text-right tabular-nums">{c.accuracy_percent}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Not enough attempt data yet.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI usage</CardTitle>
            <CardDescription>{aiUsage?.total_requests ?? 0} AI Gateway requests logged.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-semibold">${aiUsage?.total_cost_usd.toFixed(4) ?? "0.0000"}</span>
              <span className="text-sm text-muted-foreground">estimated cost</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Success: {aiUsage?.success_rate_percent ?? 0}%</Badge>
              <Badge variant="outline">Fallback: {aiUsage?.fallback_rate_percent ?? 0}%</Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">AI usage by agent</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground">
                    <th className="p-1.5 font-normal">Agent</th>
                    <th className="p-1.5 text-right font-normal">Requests</th>
                    <th className="p-1.5 text-right font-normal">Cost</th>
                    <th className="p-1.5 text-right font-normal">Avg latency</th>
                    <th className="p-1.5 text-right font-normal">Success</th>
                  </tr>
                </thead>
                <tbody>
                  {aiUsage?.by_agent.map((a) => (
                    <tr key={a.agent_type} className="border-t">
                      <td className="p-1.5">{a.agent_type}</td>
                      <td className="p-1.5 text-right tabular-nums">{a.requests}</td>
                      <td className="p-1.5 text-right tabular-nums">${a.total_cost_usd.toFixed(4)}</td>
                      <td className="p-1.5 text-right tabular-nums">{a.average_latency_ms}ms</td>
                      <td className="p-1.5 text-right tabular-nums">{a.success_rate_percent}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
