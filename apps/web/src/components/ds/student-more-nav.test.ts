import { describe, expect, it } from "vitest";

import { MOBILE_MORE_LINKS, MOBILE_MORE_SECTIONS } from "@/components/ds/student-bottom-nav";
import {
  STUDENT_MORE_LINKS,
  STUDENT_MORE_SECTIONS,
} from "@/components/ds/student-more-nav";

describe("Student More nav (shared source of truth)", () => {
  it("mobile bottom-nav sections are identity-shared with the DS source", () => {
    // The re-export in student-bottom-nav.tsx must NOT clone — the desktop
    // AppHeader and the mobile More sheet must reference the same object
    // so a future edit cannot silently apply to only one shell.
    expect(MOBILE_MORE_SECTIONS).toBe(STUDENT_MORE_SECTIONS);
    expect(MOBILE_MORE_LINKS).toBe(STUDENT_MORE_LINKS);
  });

  it("shape is preserved: two labeled sections and a flat href list", () => {
    expect(STUDENT_MORE_SECTIONS.map((s) => s.label)).toEqual([
      "Study tools",
      "Account",
    ]);
    expect(STUDENT_MORE_LINKS.map((l) => l.href)).toEqual([
      "/student/flashcards",
      "/student/mock-tests",
      "/student/questions",
      "/student/attempts",
      "/student/study-plan",
      "/student/profile",
      "/student/settings",
    ]);
  });

  it("every href starts with /student and every label is non-empty", () => {
    for (const link of STUDENT_MORE_LINKS) {
      expect(link.href.startsWith("/student/")).toBe(true);
      expect(link.label.length).toBeGreaterThan(0);
    }
  });
});
