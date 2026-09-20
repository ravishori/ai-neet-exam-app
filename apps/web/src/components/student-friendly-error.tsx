"use client";

import Link from "next/link";
import { AlertTriangle } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type StudentFriendlyErrorProps = {
  title?: string;
  description?: string;
  reference?: string | null;
  onRetry?: () => void;
  dashboardHref?: string;
  className?: string;
};

/**
 * Student-safe error surface — never render stack traces, paths, or SQL here.
 */
export function StudentFriendlyError({
  title = "Something went wrong",
  description = "We couldn't load this page right now. Your progress is safe. Please try again. If the problem continues, our system will automatically record the issue for the support team.",
  reference,
  onRetry,
  dashboardHref = "/student/dashboard",
  className,
}: StudentFriendlyErrorProps) {
  return (
    <main
      className={cn(
        "mx-auto flex w-full max-w-lg flex-1 flex-col items-center justify-center gap-5 px-4 py-16 text-center animate-fade-slide-up",
        className,
      )}
      role="alert"
    >
      <span className="flex size-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <AlertTriangle className="size-5" aria-hidden />
      </span>
      <div className="space-y-2">
        <h1 className="font-heading text-2xl font-semibold tracking-tight text-balance">{title}</h1>
        <p className="text-sm leading-relaxed text-muted-foreground">{description}</p>
        {reference ? (
          <p className="text-xs text-muted-foreground">
            Reference: <span className="font-mono tabular-nums text-foreground">{reference}</span>
          </p>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {onRetry ? (
          <Button type="button" className="min-h-11" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
        <Link href={dashboardHref} className={cn(buttonVariants({ variant: "outline" }), "min-h-11")}>
          Go to Dashboard
        </Link>
      </div>
    </main>
  );
}
