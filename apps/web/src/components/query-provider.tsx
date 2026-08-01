"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "@/lib/api-client";

function shouldRetry(failureCount: number, error: unknown): boolean {
  // Client errors (4xx) won't succeed on retry — only network/5xx errors might.
  if (error instanceof ApiError && error.status < 500) return false;
  return failureCount < 2;
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { refetchOnWindowFocus: false, retry: shouldRetry, networkMode: "always" },
          mutations: { networkMode: "always" },
        },
      })
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
