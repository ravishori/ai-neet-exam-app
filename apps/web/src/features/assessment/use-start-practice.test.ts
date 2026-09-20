import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api-client";
import { practiceStartMessage } from "@/features/assessment/use-start-practice";

describe("practiceStartMessage", () => {
  it("explains network failures clearly", () => {
    const msg = practiceStartMessage(new ApiError("down", "NETWORK_ERROR", 0));
    expect(msg.toLowerCase()).toContain("reach");
  });

  it("preserves no-questions copy", () => {
    const msg = practiceStartMessage(new ApiError("None left", "NO_QUESTIONS_AVAILABLE", 422));
    expect(msg).toContain("None left");
  });

  it("asks unauthenticated users to log in", () => {
    const msg = practiceStartMessage(new ApiError("auth", "UNAUTHORIZED", 401));
    expect(msg.toLowerCase()).toContain("log in");
  });

  it("uses generic load failure for 5xx", () => {
    const msg = practiceStartMessage(new ApiError("boom", "SERVER", 500));
    expect(msg.toLowerCase()).toContain("could not be loaded");
  });

  it("falls back for unknown errors", () => {
    expect(practiceStartMessage(new Error("boom"))).toMatch(/unable to start practice/i);
  });
});
