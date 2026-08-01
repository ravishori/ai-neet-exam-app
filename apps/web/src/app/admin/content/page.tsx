"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConceptPicker } from "@/components/concept-picker";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api-client";
import { aiApi } from "@/features/ai/api";
import { cmsApi, type WorkflowState } from "@/features/cms/api";

const STATE_VARIANT: Record<WorkflowState, "default" | "secondary" | "outline" | "destructive"> = {
  DRAFT: "outline",
  IN_REVIEW: "secondary",
  CHANGES_REQUESTED: "destructive",
  APPROVED: "secondary",
  PUBLISHED: "default",
  ARCHIVED: "outline",
};

export default function ContentListPage() {
  const router = useRouter();
  const { data: items, isLoading } = useQuery({ queryKey: ["cms", "list"], queryFn: () => cmsApi.list() });
  const [genConceptId, setGenConceptId] = useState<string | null>(null);

  const generate = useMutation({
    mutationFn: () => aiApi.generateQuestion({ concept_id: genConceptId! }),
    onSuccess: (item) => router.push(`/admin/content/${item.id}`),
  });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  return (
    <main className="flex-1 px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Content</h1>
        <Link href="/admin/content/new" className={cn(buttonVariants())}>
          New content
        </Link>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Generate with AI</CardTitle>
          <CardDescription>Pick a concept and let the Question Generator agent draft a question for review.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {generate.isError && (
            <Alert variant="destructive">
              <AlertDescription>{generate.error instanceof ApiError ? generate.error.message : "Something went wrong"}</AlertDescription>
            </Alert>
          )}
          <ConceptPicker value={genConceptId} onChange={setGenConceptId} />
          <Button
            className="w-fit"
            disabled={!genConceptId || generate.isPending}
            onClick={() => generate.mutate()}
          >
            {generate.isPending ? "Generating…" : "Generate question"}
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-3">
        {items?.map((item) => (
          <Link key={item.id} href={`/admin/content/${item.id}`}>
            <Card className="transition-colors hover:bg-muted">
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <div>
                  <CardTitle className="text-base">{item.title}</CardTitle>
                  <p className="text-sm text-muted-foreground">{item.content_type}</p>
                </div>
                <Badge variant={STATE_VARIANT[item.status]}>{item.status}</Badge>
              </CardHeader>
            </Card>
          </Link>
        ))}
        {items?.length === 0 && <p className="text-sm text-muted-foreground">No content yet.</p>}
      </div>
    </main>
  );
}
