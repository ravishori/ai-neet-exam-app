import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { FieldSelect } from "@/components/ui/field-select";
import { MOBILE_MORE_LINKS } from "@/components/ds/student-bottom-nav";

describe("Phase A5 FieldSelect", () => {
  it("forwards value, onChange, disabled, and id", () => {
    const onChange = () => {};
    render(
      <FieldSelect id="pilot-select" value="a" onChange={onChange} disabled aria-label="Pilot">
        <option value="a">A</option>
        <option value="b">B</option>
      </FieldSelect>,
    );
    const el = screen.getByLabelText("Pilot") as HTMLSelectElement;
    expect(el.id).toBe("pilot-select");
    expect(el.value).toBe("a");
    expect(el.disabled).toBe(true);
    expect(el.getAttribute("data-slot")).toBe("field-select");
  });
});

describe("Phase A8 mobile More IA (shell contract)", () => {
  it("includes Flashcards, Mock Tests, Questions, Attempts, Study Plan, Profile, Settings", () => {
    const hrefs = MOBILE_MORE_LINKS.map((l) => l.href);
    expect(hrefs).toEqual([
      "/student/flashcards",
      "/student/mock-tests",
      "/student/questions",
      "/student/attempts",
      "/student/study-plan",
      "/student/profile",
      "/student/settings",
    ]);
  });
});
