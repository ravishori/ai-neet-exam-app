"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MasteryBar } from "@/components/mastery-badge";
import { cn } from "@/lib/utils";
import { useMe } from "@/features/auth/use-auth";
import { learningApi } from "@/features/learning/api";

export default function StudentDashboardPage() {
  const { data: user, isLoading } = useMe();
  const { data: overview } = useQuery({ queryKey: ["learning", "overview"], queryFn: learningApi.overview });

  return (
    <main className="flex flex-1 flex-col items-center gap-6 px-6 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">
          {isLoading ? "Loading…" : `Welcome, ${user?.first_name ?? user?.email}`}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Revision queue and recommended practice land once the Recommendation module exists.
        </p>
      </div>

      <Link href="/student/subjects" className={cn(buttonVariants())}>
        Browse subjects
      </Link>

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
