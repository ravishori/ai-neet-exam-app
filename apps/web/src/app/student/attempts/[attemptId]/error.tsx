"use client";

import { useEffect } from "react";

import { StudentFriendlyError } from "@/components/student-friendly-error";

export default function AttemptError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("attempt_route_error", { digest: error.digest, name: error.name });
  }, [error]);

  return (
    <StudentFriendlyError
      title="Something went wrong"
      description="We couldn't load this practice session right now. Your progress is safe. Please try again."
      reference={error.digest ?? null}
      onRetry={() => reset()}
    />
  );
}
