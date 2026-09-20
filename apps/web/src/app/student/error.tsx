"use client";

import { useEffect } from "react";

import { StudentFriendlyError } from "@/components/student-friendly-error";

export default function StudentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("student_route_error", { digest: error.digest, name: error.name });
  }, [error]);

  return (
    <StudentFriendlyError
      title="Something went wrong"
      description="We couldn't load this page right now. Your progress is safe. Please try again. If the problem continues, our system will automatically record the issue for the support team."
      reference={error.digest ?? null}
      onRetry={() => reset()}
    />
  );
}
