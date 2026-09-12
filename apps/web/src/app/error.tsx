"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Digest is a Next.js production error id — safe to surface; never log stack to users.
    console.error("app_error", { digest: error.digest, name: error.name });
  }, [error]);

  const reference = error.digest ?? "UNKNOWN";

  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <h1 className="font-heading text-2xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        We couldn&apos;t complete this request right now.
        <br />
        Reference ID: <span className="font-mono tabular-nums text-foreground">{reference}</span>
        <br />
        Please try again. If the problem continues, contact support with this reference.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          onClick={() => reset()}
          className="inline-flex h-9 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
        >
          Try again
        </button>
        <Link
          href="/student/dashboard"
          className="inline-flex h-9 items-center rounded-lg border px-4 text-sm font-medium"
        >
          Go to dashboard
        </Link>
      </div>
    </main>
  );
}
