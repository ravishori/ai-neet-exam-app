"use client";

import { ShieldAlert } from "lucide-react";

import { AppHeader, type NavSection } from "@/components/app-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/features/auth/use-auth";

/** Presentation-only grouping — all hrefs unchanged (Phase A10). */
const ADMIN_PRIMARY = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/content", label: "Questions" },
  { href: "/admin/ai-review", label: "Editorial Review" },
  { href: "/admin/content/review-queue", label: "Review Queue" },
];

const ADMIN_MORE_SECTIONS: NavSection[] = [
  {
    label: "Content Ops",
    links: [
      { href: "/admin/knowledge-units", label: "Knowledge Units" },
      { href: "/admin/ingestion", label: "PDFs" },
      { href: "/admin/visual-assets", label: "Visual Assets" },
      { href: "/admin/factory-review", label: "Factory Review" },
      { href: "/admin/p2-3/human-gold", label: "Human Gold Sandbox" },
    ],
  },
  {
    label: "Platform",
    links: [
      { href: "/admin/search", label: "Search Console" },
      { href: "/admin/audit-logs", label: "Audit Logs" },
      { href: "/admin/users", label: "Users" },
      { href: "/admin/coverage", label: "Coverage" },
      { href: "/admin/analytics", label: "Analytics" },
    ],
  },
];

const ADMIN_ROLES = new Set(["SUPER_ADMIN", "ADMIN", "CONTENT_MANAGER"]);

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading } = useMe();

  if (isLoading) {
    return (
      <div className="page-atmosphere flex flex-1 flex-col">
        <div className="border-b border-glass-border bg-glass/90 px-4 py-3 backdrop-blur-md sm:px-6">
          <Skeleton className="h-6 w-32" />
        </div>
        <div className="flex-1 px-4 py-8 sm:px-6">
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  }

  if (!user || !user.roles.some((role) => ADMIN_ROLES.has(role))) {
    return (
      <div className="page-atmosphere flex flex-1 flex-col">
        <AppHeader brandHref="/admin" navLabel="Admin" primaryLinks={[]} />
        <main className="flex flex-1 items-center justify-center px-6 py-12">
          <EmptyState
            icon={ShieldAlert}
            title="You don't have access to the admin portal"
            description="This area is restricted to Admin and Content Manager accounts. If you believe this is a mistake, contact a platform administrator."
          />
        </main>
      </div>
    );
  }

  return (
    <div className="page-atmosphere flex flex-1 flex-col">
      <AppHeader
        brandHref="/admin"
        navLabel="Admin"
        primaryLinks={ADMIN_PRIMARY}
        moreSections={ADMIN_MORE_SECTIONS}
      />
      {children}
    </div>
  );
}
