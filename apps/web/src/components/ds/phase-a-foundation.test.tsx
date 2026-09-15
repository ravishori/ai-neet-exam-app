import { describe, expect, it } from "vitest";

import { resolveSubjectTheme } from "@/components/ds/subject-theme";
import { badgeVariants } from "@/components/ui/badge";

describe("Phase A foundation — subject theme", () => {
  it("maps Physics / Chemistry to distinct families", () => {
    expect(resolveSubjectTheme("Physics")).toBe("physics");
    expect(resolveSubjectTheme("Chemistry")).toBe("chemistry");
  });

  it("maps Biology, Botany, and Zoology to the biology family", () => {
    expect(resolveSubjectTheme("Biology")).toBe("biology");
    expect(resolveSubjectTheme("Botany")).toBe("biology");
    expect(resolveSubjectTheme("Zoology")).toBe("biology");
  });

  it("returns neutral when unset", () => {
    expect(resolveSubjectTheme(null)).toBe("neutral");
    expect(resolveSubjectTheme(undefined)).toBe("neutral");
    expect(resolveSubjectTheme("")).toBe("neutral");
  });
});

describe("Phase A foundation — badge semantic variants", () => {
  it("exposes success and warning status variants without subject hues", () => {
    const success = badgeVariants({ variant: "success" });
    const warning = badgeVariants({ variant: "warning" });
    const destructive = badgeVariants({ variant: "destructive" });

    expect(success).toContain("bg-success");
    expect(warning).toContain("bg-warning");
    expect(destructive).toContain("bg-destructive");
    expect(success).not.toMatch(/subject-/);
    expect(warning).not.toMatch(/subject-/);
  });
});
