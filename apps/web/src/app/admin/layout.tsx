"use client";

import { ShieldAlert } from "lucide-react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useMe } from "@/features/auth/use-auth";

const ADMIN_LINKS = [
  { href: "/admin", label: "Dashboard" },
  { href: "/admin/content", label: "Questions" },
  { href: "/admin/knowledge-units", label: "Knowledge Units" },
  { href: "/admin/ingestion", label: "PDFs" },
  { href: "/admin/visual-assets", label: "Visual Assets" },
  { href: "/admin/ai-review", label: "Editorial Review" },
  { href: "/admin/factory-review", label: "Factory Review" },
  { href: "/admin/p2-3/human-gold", label: "Human Gold Sandbox" },
  { href: "/admin/search", label: "Search Console" },
  { href: "/admin/audit-logs", label: "Audit Logs" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/coverage", label: "Coverage" },
  { href: "/admin/analytics", label: "Analytics" },
];

const ADMIN_ROLES = new Set(["SUPER_ADMIN", "ADMIN", "CONTENT_MANAGER"]);

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { data: user, isLoading } = useMe();

  if (isLoading) {
    return (
      <div className="page-atmosphere flex flex-1 flex-col">
        <div className="border-b border-glass-border bg-glass/80 px-4 py-3 backdrop-blur-xl sm:px-6">
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
        <AppHeader links={[]} />
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
      <AppHeader links={ADMIN_LINKS} />
      {children}
    </div>
  );
}
