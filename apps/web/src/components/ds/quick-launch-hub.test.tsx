import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { QuickLaunchHub } from "@/components/ds/quick-launch-hub";

const EXPECTED_HREFS = [
  "/student/practice",
  "/student/mock-tests",
  "/student/subjects",
  "/student/questions",
  "/student/study-plan",
  "/student/flashcards",
  "/student/analytics",
] as const;

describe("FRONTEND-A12 QuickLaunchHub", () => {
  it("renders deterministic destinations and stable link classnames", () => {
    const { container, rerender } = render(<QuickLaunchHub />);

    const hub = container.querySelector("[data-quick-launch-hub]");
    expect(hub).toBeTruthy();

    const links = within(hub as HTMLElement).getAllByRole("link");
    expect(links).toHaveLength(EXPECTED_HREFS.length);
    expect(links.map((a) => a.getAttribute("href"))).toEqual([...EXPECTED_HREFS]);

    for (const href of EXPECTED_HREFS) {
      const link = container.querySelector(`[data-quick-launch-item="${href}"]`);
      expect(link).toBeTruthy();
      expect(link).toHaveAttribute("href", href);
      expect(link?.className).toBe(
        "hover-lift surface-glass group flex items-start gap-3 rounded-2xl p-4 outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
      );
    }

    // Re-render must keep the same href order / classes (no unstable ids).
    rerender(<QuickLaunchHub />);
    const again = within(
      container.querySelector("[data-quick-launch-hub]") as HTMLElement,
    ).getAllByRole("link");
    expect(again.map((a) => a.getAttribute("href"))).toEqual([...EXPECTED_HREFS]);
    expect(container.querySelectorAll("[id^='base-ui-']")).toHaveLength(0);
  });

  it("exposes accessible labels for each launch tile", () => {
    render(<QuickLaunchHub />);
    expect(
      screen.getByRole("link", { name: /Practice arena/i }),
    ).toHaveAttribute("href", "/student/practice");
    expect(screen.getByRole("link", { name: /Mock test/i })).toHaveAttribute(
      "href",
      "/student/mock-tests",
    );
    expect(screen.getByRole("link", { name: /Flashcards/i })).toHaveAttribute(
      "href",
      "/student/flashcards",
    );
  });
});
