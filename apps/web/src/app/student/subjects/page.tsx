"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";

import {
  PageHeader,
  StudentPage,
  SubjectChip,
  SurfaceCard,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { academicApi } from "@/features/academic/api";

export default function SubjectsPage() {
  const { data: subjects, isLoading } = useQuery({ queryKey: ["academic", "subjects"], queryFn: academicApi.subjects });

  return (
    <StudentPage width="lg">
      <PageHeader
        eyebrow="Curriculum"
        title="Subjects"
        description="Browse NEET subjects, then drill into chapters and topics."
      />

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2" aria-busy="true" aria-live="polite">
          <Skeleton className="h-24 w-full rounded-2xl" />
          <Skeleton className="h-24 w-full rounded-2xl" />
          <Skeleton className="h-24 w-full rounded-2xl" />
        </div>
      ) : !subjects?.length ? (
        <EmptyState icon={BookOpen} title="No subjects yet" description="Subjects will appear once the academic catalog is seeded." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {subjects.map((subject) => (
            <Link key={subject.id} href={`/student/subjects/${subject.id}`} className="block">
              <SurfaceCard subject={subject.name} accent="left" className="h-full">
                <SurfaceCardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <SurfaceCardTitle>{subject.name}</SurfaceCardTitle>
                    <SubjectChip subject={subject.name} />
                  </div>
                  <SurfaceCardDescription>NEET</SurfaceCardDescription>
                </SurfaceCardHeader>
              </SurfaceCard>
            </Link>
          ))}
        </div>
      )}
    </StudentPage>
  );
}
