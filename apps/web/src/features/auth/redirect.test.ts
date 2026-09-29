import { describe, expect, it } from "vitest";

import { DEFAULT_AFTER_LOGIN, safeNextPath } from "./redirect";

describe("safeNextPath", () => {
  it.each([
    "/student/dashboard",
    "/student/practice?topic=optics",
    "/admin/content/review-queue",
  ])("keeps same-origin path %s", (next) => {
    expect(safeNextPath(next)).toBe(next);
  });

  it.each([null, undefined, ""])("defaults when next is %s", (next) => {
    expect(safeNextPath(next)).toBe(DEFAULT_AFTER_LOGIN);
  });

  it.each([
    "https://evil.example",
    "http://evil.example/student/dashboard",
    "//evil.example",
    "/\\evil.example",
    "javascript:alert(1)",
    "evil.example",
    "/\t/evil.example",
    "/\n/evil.example",
  ])("rejects off-site or unsafe target %j", (next) => {
    expect(safeNextPath(next)).toBe(DEFAULT_AFTER_LOGIN);
  });
});
