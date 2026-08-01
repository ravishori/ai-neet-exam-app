"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
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
  const { data: items, isLoading } = useQuery({ queryKey: ["cms", "list"], queryFn: () => cmsApi.list() });

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
