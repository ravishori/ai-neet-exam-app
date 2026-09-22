"use client";

import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { commerceApi } from "@/features/commerce/api";

/**
 * Wraps premium content and shows an upgrade state instead when the
 * backend's access-state says the student has no active trial/entitlement.
 *
 * This is a UX convenience only — the actual security boundary is the
 * backend's require_active_access() dependency on the underlying API
 * routes. A user who bypasses this component entirely (disabling JS,
 * calling the API directly) still gets a real 403 from the server; this
 * component exists purely so legitimate users see a clear message instead
 * of a broken page full of failed API calls.
 */
export function AccessGate({ children }: { children: ReactNode }) {
  const { data: access, isLoading } = useQuery({
    queryKey: ["commerce", "access-state"],
    queryFn: commerceApi.accessState,
  });

  if (isLoading) {
    return <Skeleton className="h-40 w-full" />;
  }

  if (!access || access.hasAccess) {
    return <>{children}</>;
  }

  const message =
    access.state === "TRIAL_EXPIRED"
      ? "Your free trial has ended. Choose an annual plan to continue."
      : "This feature requires an active trial or subscription.";

  return (
    <Alert>
      <AlertTitle>Upgrade required</AlertTitle>
      <AlertDescription className="flex flex-col gap-3">
        <span>{message}</span>
        <Link href="/student/profile" className={cn(buttonVariants({ variant: "default" }), "w-fit")}>
          View plans
        </Link>
      </AlertDescription>
    </Alert>
  );
}
