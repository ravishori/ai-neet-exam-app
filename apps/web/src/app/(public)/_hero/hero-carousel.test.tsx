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
      screen.getByRole("link", { name: /See This Week — Weekly Assessment/i }),
    ).toHaveAttribute("href", "/student/weekly-assessments");
  });

  it("renders exactly five feature bullets per active capability", () => {
    render(<HeroCarousel />);
    for (let i = 0; i < HERO_CAPABILITIES.length; i++) {
      // Advance to the i-th capability.
      const tablist = screen.getByRole("tablist");
      if (i > 0) {
        fireEvent.keyDown(tablist, { key: "ArrowRight" });
      }
      const list = screen.getByTestId("hero-bullets");
      const items = list.querySelectorAll("li");
      expect(items).toHaveLength(5);
      const capability = HERO_CAPABILITIES[i];
      expect(list.getAttribute("aria-label")).toMatch(new RegExp(capability.title, "i"));
      // Each bullet text matches the capability's approved copy.
      const rendered = Array.from(items).map((li) => (li.textContent ?? "").trim());
      expect(rendered).toEqual([...capability.bullets]);
    }
  });

  it("renders the active capability headline as a semantic heading level 3", () => {
    render(<HeroCarousel />);
    const h3 = screen.getByRole("heading", { level: 3, name: /Practice exactly what you need\./i });
    expect(h3).toBeInTheDocument();
    // ArrowRight → next capability's headline is still an <h3>.
    const tablist = screen.getByRole("tablist");
    screen.getByRole("tab", { name: /Custom Practice/i }).focus();
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(
      screen.getByRole("heading", { level: 3, name: /Know where you stand every week\./i }),
    ).toBeInTheDocument();
  });

  it("uses the v2.2 revised bullet copy for Weekly Assessment and Weak Topic Focus", () => {
    render(<HeroCarousel />);
    const tablist = screen.getByRole("tablist");

    // Weekly Assessment — bullet 4 revised.
    fireEvent.keyDown(tablist, { key: "ArrowRight" }); // → Weekly Assessment
    let items = Array.from(
      screen.getByTestId("hero-bullets").querySelectorAll("li"),
    ).map((li) => (li.textContent ?? "").trim());
    expect(items[3]).toBe("See which subjects the paper is weighted toward");
    expect(items).not.toContain("Identify subjects that need more attention");

    // Weak Topic Focus — bullets 2 and 4 revised.
    fireEvent.keyDown(tablist, { key: "ArrowRight" }); // → Weak Topic Focus
    items = Array.from(
      screen.getByTestId("hero-bullets").querySelectorAll("li"),
    ).map((li) => (li.textContent ?? "").trim());
    expect(items[1]).toBe("See chapter-level mastery from your attempts");
    expect(items[3]).toBe("Take the insight to your next practice session");
    expect(items).not.toContain("Identify chapters that need more practice");
    expect(items).not.toContain("Focus your next practice session intelligently");
  });

  it("removes the old 'Trinetra AI Learning OS' eyebrow while keeping the H1 + trust line", () => {
    render(<HeroCarousel />);
    expect(screen.queryByText(/Trinetra AI Learning OS/i)).toBeNull();
    // H1 unchanged; trust line still present.
    expect(
      screen.getByRole("heading", { level: 1, name: /Your NEET preparation\. Built around you\./ }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/NCERT-aligned preparation for NEET aspirants in India\./),
    ).toBeInTheDocument();
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

  it("stays fully navigable under prefers-reduced-motion: reduce", () => {
    const originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === "(prefers-reduced-motion: reduce)",
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    try {
      render(<HeroCarousel />);
      // Keyboard navigation must not depend on transitions.
      const tablist = screen.getByRole("tablist");
      screen.getByRole("tab", { name: /Custom Practice/i }).focus();
      fireEvent.keyDown(tablist, { key: "ArrowRight" });
      expect(
        screen.getByRole("tab", { name: /Weekly Assessment/i }),
      ).toHaveAttribute("aria-selected", "true");
      // CTA remains reachable + labelled.
      expect(
        screen.getByRole("link", { name: /See This Week — Weekly Assessment/i }),
      ).toHaveAttribute("href", "/student/weekly-assessments");
    } finally {
      if (originalMatchMedia) {
        Object.defineProperty(window, "matchMedia", {
          value: originalMatchMedia,
          writable: true,
          configurable: true,
        });
      }
    }
  });

  it("announces the active tile via a polite live region and updates on ArrowRight", () => {
    render(<HeroCarousel />);
    const live = screen.getByTestId("hero-live-announcement");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(live).toHaveAttribute("role", "status");
    expect(live).toHaveClass("sr-only");
    expect(live).toHaveTextContent(/Now viewing:\s*Custom Practice, tile 1 of 6/i);

    const tablist = screen.getByRole("tablist");
    screen.getByRole("tab", { name: /Custom Practice/i }).focus();
    fireEvent.keyDown(tablist, { key: "ArrowRight" });
    expect(live).toHaveTextContent(/Now viewing:\s*Weekly Assessment, tile 2 of 6/i);
  });

  it("renders one next/image per capability with only the first tile priority-loaded", () => {
    render(<HeroCarousel />);
    // Six previews, each contains exactly one <img>.
    const imgs = Array.from(document.querySelectorAll("img")) as HTMLImageElement[];
    expect(imgs).toHaveLength(6);
    // Every image has meaningful alt text (not the capability slogan).
    for (const img of imgs) {
      expect(img.getAttribute("alt")).toBeTruthy();
      expect(img.getAttribute("alt")).not.toMatch(/exactly what you need|know where you stand|comes next/i);
    }
    // Only the first tile's image is priority (loading not "lazy").
    // next/image renders `loading="lazy"` on non-priority images.
    const lazyCount = imgs.filter((i) => i.getAttribute("loading") === "lazy").length;
    expect(lazyCount).toBe(5);
  });

  it("marks example-data previews with an accessible Example chip", () => {
    render(<HeroCarousel />);
    const chips = document.querySelectorAll('[data-testid="hero-example-chip"]');
    expect(chips.length).toBe(2);
    for (const chip of Array.from(chips)) {
      expect(chip.getAttribute("aria-label") ?? "").toMatch(/example data/i);
    }
  });
});
