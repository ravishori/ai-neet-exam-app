"use client";

import { useEffect } from "react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function AttemptError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("attempt_route_error", { message: error.message, digest: error.digest });
  }, [error]);

  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center gap-4 px-4 py-12">
      <Alert variant="destructive" role="alert">
        <AlertTitle>Unable to continue this practice session</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>A runtime error interrupted the attempt view. You can retry or start a new session from Practice.</p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={reset}>
              Retry
            </Button>
            <Link href="/student/practice" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex")}>
              Practice arena
            </Link>
            <Link href="/student/dashboard" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "inline-flex")}>
              Dashboard
            </Link>
          </div>
        </AlertDescription>
      </Alert>
    </main>
  );
}
