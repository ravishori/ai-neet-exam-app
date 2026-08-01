"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { assessmentApi } from "@/features/assessment/api";

export default function AttemptsHistoryPage() {
  const { data: attempts, isLoading } = useQuery({ queryKey: ["assessment", "attempts"], queryFn: assessmentApi.listAttempts });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 px-6 py-10">
      <h1 className="mb-6 text-xl font-semibold">My attempts</h1>
      <div className="grid gap-3">
        {attempts?.map((a) => (
          <Link key={a.id} href={`/student/attempts/${a.id}`}>
            <Card className="transition-colors hover:bg-muted">
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base">{new Date(a.started_at).toLocaleString()}</CardTitle>
                <div className="flex items-center gap-2">
                  {a.status === "SUBMITTED" && <span className="text-sm text-muted-foreground">Score: {a.score}</span>}
                  <Badge variant={a.status === "SUBMITTED" ? "default" : "secondary"}>{a.status}</Badge>
                </div>
              </CardHeader>
            </Card>
          </Link>
        ))}
        {attempts?.length === 0 && <p className="text-sm text-muted-foreground">No attempts yet.</p>}
      </div>
    </main>
  );
}
