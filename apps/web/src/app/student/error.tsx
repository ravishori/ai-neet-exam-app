"use client";

import { useEffect } from "react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function StudentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("student_route_error", { message: error.message, digest: error.digest });
  }, [error]);

  return (
    <main className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center gap-4 px-4 py-12">
      <Alert variant="destructive" role="alert">
        <AlertTitle>Something went wrong</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>We could not render this page. Your practice data was not deleted — try again or return to the dashboard.</p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={reset}>
              Try again
            </Button>
            <Link href="/student/dashboard" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "inline-flex")}>
              Dashboard
            </Link>
          </div>
        </AlertDescription>
      </Alert>
    </main>
  );
}
