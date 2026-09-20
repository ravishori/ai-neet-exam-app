"use client";

import { useEffect } from "react";

/**
 * Auth cookies are set by the API on 127.0.0.1 (NEXT_PUBLIC_API_URL).
 * They are host-scoped across ports, so 127.0.0.1:3000 can read them, but
 * localhost:3000 cannot — login succeeds then middleware bounces back to /login.
 */
export function LoopbackHostGuard() {
  useEffect(() => {
    if (window.location.hostname !== "localhost") return;
    const next = new URL(window.location.href);
    next.hostname = "127.0.0.1";
    window.location.replace(next.toString());
  }, []);

  return null;
}
