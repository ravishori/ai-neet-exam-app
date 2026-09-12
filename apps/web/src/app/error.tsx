"use client";

import { useEffect } from "react";

import { StudentFriendlyError } from "@/components/student-friendly-error";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Digest only — never log stacks or filesystem paths to the console in a way that could leak to UI.
    console.error("app_error", { digest: error.digest, name: error.name });
  }, [error]);

  return (
    <StudentFriendlyError
      reference={error.digest ?? null}
      onRetry={() => reset()}
    />
  );
}
