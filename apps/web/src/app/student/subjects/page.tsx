"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { academicApi } from "@/features/academic/api";

export default function SubjectsPage() {
  const { data: subjects, isLoading } = useQuery({ queryKey: ["academic", "subjects"], queryFn: academicApi.subjects });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 px-6 py-10">
      <h1 className="mb-6 text-xl font-semibold">Subjects</h1>
      <div className="grid gap-3 sm:grid-cols-2">
        {subjects?.map((subject) => (
          <Link key={subject.id} href={`/student/subjects/${subject.id}`}>
            <Card className="transition-colors hover:bg-muted">
              <CardHeader>
                <CardTitle>{subject.name}</CardTitle>
                <CardDescription>NEET</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </main>
  );
}
