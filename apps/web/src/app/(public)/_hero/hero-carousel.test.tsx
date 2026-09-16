import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", async () => {
  const React = await import("react");
  return {
    default: React.forwardRef<HTMLAnchorElement, React.AnchorHTMLAttributes<HTMLAnchorElement>>(
      function LinkStub({ children, ...props }, ref) {
        return <a ref={ref} {...props}>{children}</a>;
      },
    ),
  };
});

import { HERO_CAPABILITIES } from "./data";
import { HeroCarousel } from "./HeroCarousel";

describe("Homepage hero (M3A)", () => {
  beforeEach(() => {
    Object.defineProperty(window, "innerWidth", { value: 375, configurable: true });
    Object.defineProperty(window, "innerHeight", { value: 812, configurable: true });
  });

  it("renders exactly one H1 with the M3A copy and the subcopy", () => {
    render(<HeroCarousel />);
    const h1s = screen.getAllByRole("heading", { level: 1 });
    expect(h1s).toHaveLength(1);
    expect(h1s[0]).toHaveTextContent(/Your NEET preparation\. Built around you\./);
    expect(
      screen.getByText(/Practice what matters\. Understand where you stand\./i),
    ).toBeInTheDocument();
  });

  it("exposes six capability tabs pointing at the approved existing routes", () => {
    render(<HeroCarousel />);
    for (const cap of HERO_CAPABILITIES) {
      expect(screen.getByRole("tab", { name: new RegExp(cap.title, "i") })).toBeInTheDocument();
    }
    expect(HERO_CAPABILITIES.map((c) => c.href)).toEqual([
      "/student/practice",
      "/student/weekly-assessments",
      "/student/analytics",
      "/student/dashboard",
      "/student/mock-tests",
      "/login",
    ]);
  });

  it("changes the active tab and CTA target on ArrowRight", () => {
    render(<HeroCarousel />);
    const tablist = screen.getByRole("tablist");
    screen.getByRole("tab", { name: /Custom Practice/i }).focus();
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(
      screen.getByRole("tab", { name: /Weekly Assessment/i }),
    ).toHaveAttribute("aria-selected", "true");
    expect(
      screen.getByRole("link", { name: /See this week — Weekly Assessment/i }),
    ).toHaveAttribute("href", "/student/weekly-assessments");
  });

  it("Home / End keys jump to first and last tab", () => {
    render(<HeroCarousel />);
    const tablist = screen.getByRole("tablist");
    fireEvent.keyDown(tablist, { key: "End" });
    expect(screen.getByRole("tab", { name: /Study Coach/i })).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(tablist, { key: "Home" });
    expect(screen.getByRole("tab", { name: /Custom Practice/i })).toHaveAttribute("aria-selected", "true");
  });

  it("every tab meets the touch-target minimum via the touch-target / min-h-12 class", () => {
    render(<HeroCarousel />);
    for (const cap of HERO_CAPABILITIES) {
      const tab = screen.getByRole("tab", { name: new RegExp(cap.title, "i") });
      expect(tab.className).toMatch(/touch-target|min-h-12/);
    }
  });

  it("uses placeholder previews (no <img> loaded) and marks them as such", () => {
    render(<HeroCarousel />);
    expect(document.querySelector('[data-preview-placeholder="true"]')).not.toBeNull();
    expect(document.querySelectorAll("img").length).toBe(0);
  });
});
