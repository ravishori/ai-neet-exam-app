"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BookOpenCheck,
  ClipboardList,
  Database,
  FileSearch,
  Flag,
  Image as ImageIcon,
  ScrollText,
  Sparkles,
  Upload,
  Users,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SurfaceCard, SurfaceCardContent } from "@/components/ds";
import { adminApi } from "@/features/admin/api";

const MODULES = [
  { href: "/admin/content", label: "Question Management", description: "Review, publish, and triage reports", icon: ClipboardList },
  { href: "/admin/knowledge-units", label: "Knowledge Units", description: "Structured facts extracted from PDFs", icon: Database },
  { href: "/admin/ingestion", label: "PDF Management", description: "Upload and track ingestion jobs", icon: Upload },
  { href: "/admin/visual-assets", label: "Visual Asset Review", description: "Approve or reject detected diagrams", icon: ImageIcon },
  { href: "/admin/ai-review", label: "Editorial Review", description: "Human ECAEP SME queue — AI assist only", icon: Sparkles },
  { href: "/admin/search", label: "Search Console", description: "Reindex and inspect search relevance", icon: FileSearch },
  { href: "/admin/audit-logs", label: "Audit Logs", description: "Every admin action, who and when", icon: ScrollText },
  { href: "/admin/users", label: "Users & Roles", description: "Accounts, roles, and permissions", icon: Users },
];

function KpiTile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <SurfaceCard lift accent="none" className="p-0">
      <SurfaceCardContent className="flex flex-col gap-1 pt-5">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <span className="font-heading font-mono text-2xl font-semibold tabular-nums text-foreground">{value}</span>
        {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
      </SurfaceCardContent>
    </SurfaceCard>
  );
}

export default function AdminDashboardPage() {
  const { data, isLoading } = useQuery({ queryKey: ["admin", "dashboard"], queryFn: adminApi.dashboard });

  const published = data?.content_by_status.PUBLISHED ?? 0;
  const pendingReview = (data?.content_by_status.IN_REVIEW ?? 0) + (data?.content_by_status.CHANGES_REQUESTED ?? 0);
  const activeIngestionJobs = Object.entries(data?.ingestion_by_status ?? {})
    .filter(([status]) => !["COMPLETED", "FAILED"].includes(status))
    .reduce((sum, [, count]) => sum + count, 0);

  return (
    <main className="flex-1 px-4 py-8 sm:px-6 animate-fade-slide-up">
      <div className="mx-auto flex max-w-6xl flex-col gap-8">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">Operations</p>
          <h1 className="font-heading text-2xl font-bold tracking-tight">Admin Dashboard</h1>
          <p className="text-sm text-muted-foreground">Content operations at a glance — ECAEP workflow unchanged.</p>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-busy="true" aria-live="polite">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <KpiTile label="Total Users" value={data?.total_users ?? 0} />
            <KpiTile label="Published Questions" value={published} />
            <KpiTile label="Pending Review" value={pendingReview} hint="in review + changes requested" />
            <KpiTile label="Pending Visual Assets" value={data?.pending_visual_assets ?? 0} />
            <KpiTile label="Open Reports" value={data?.open_content_reports ?? 0} />
            <KpiTile label="Active Ingestion Jobs" value={activeIngestionJobs} />
          </div>
        )}

        <Card className="surface-glass border-0">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="size-4 text-primary" aria-hidden="true" />
              <CardTitle className="text-sm">AI Gateway Usage</CardTitle>
            </div>
            <CardDescription>Total requests and estimated cost across every AI agent.</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-6 text-sm">
            <span>
              <span className="font-semibold tabular-nums">{data?.ai_total_requests ?? 0}</span>{" "}
              <span className="text-muted-foreground">requests</span>
            </span>
            <span>
              <span className="font-semibold tabular-nums">${(data?.ai_total_cost_usd ?? 0).toFixed(4)}</span>{" "}
              <span className="text-muted-foreground">estimated cost</span>
            </span>
          </CardContent>
        </Card>

        <div>
          <h2 className="mb-3 font-heading text-sm font-semibold text-muted-foreground">Modules</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {MODULES.map((mod) => (
              <Link key={mod.href} href={mod.href} className="hover-lift block">
                <SurfaceCard lift={false} accent="none" className="h-full">
                  <SurfaceCardContent className="flex flex-col gap-2 pt-5">
                    <mod.icon className="size-5 text-primary" aria-hidden="true" />
                    <span className="text-sm font-medium text-foreground">{mod.label}</span>
                    <span className="text-xs text-muted-foreground">{mod.description}</span>
                  </SurfaceCardContent>
                </SurfaceCard>
              </Link>
            ))}
          </div>
        </div>

        {data && data.open_content_reports > 0 && (
          <Card className="border-amber-500/40 bg-amber-50 dark:bg-amber-950/30">
            <CardContent className="flex items-center gap-3 pt-6 text-sm">
              <Flag className="size-4 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
              <span>
                <Link href="/admin/content?tab=reports" className="font-medium underline underline-offset-2">
                  {data.open_content_reports} open content report{data.open_content_reports === 1 ? "" : "s"}
                </Link>{" "}
                need triage.
              </span>
            </CardContent>
          </Card>
        )}

        {data && data.pending_visual_assets > 0 && (
          <Card className="border-blue-500/40 bg-blue-50 dark:bg-blue-950/30">
            <CardContent className="flex items-center gap-3 pt-6 text-sm">
              <BookOpenCheck className="size-4 shrink-0 text-blue-600 dark:text-blue-400" aria-hidden="true" />
              <span>
                <Link href="/admin/visual-assets" className="font-medium underline underline-offset-2">
                  {data.pending_visual_assets} visual asset{data.pending_visual_assets === 1 ? "" : "s"}
                </Link>{" "}
                awaiting review.
              </span>
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}
