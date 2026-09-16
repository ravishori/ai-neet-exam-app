import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

import { HowItFitsTogether } from "./HowItFitsTogether";

const VERIFIED_ROUTES = new Set(["/student/analytics", "/student/weekly-assessments"]);

describe("HowItFitsTogether (P1-B trust block)", () => {
  it("renders the section with its accessible heading", () => {
    render(<HowItFitsTogether />);
    const heading = screen.getByRole("heading", { level: 2, name: /Built on three things/i });
    expect(heading).toBeInTheDocument();
    // The heading id is referenced by the section's aria-labelledby.
    const section = heading.closest("section");
    expect(section).toHaveAttribute("aria-labelledby", heading.id);
  });

  it("renders exactly three cards with the expected titles", () => {
    render(<HowItFitsTogether />);
    const titles = screen
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent?.trim() ?? "");
    expect(titles).toHaveLength(3);
    expect(titles).toEqual([
      "Every MCQ traces to an NCERT paragraph",
      "Your practice adapts to your weak chapters",
      "Weekly recap, generated for you",
    ]);
  });

  it("only links to verified existing student routes", () => {
    render(<HowItFitsTogether />);
    const links = screen.getAllByRole("link");
    for (const link of links) {
      const href = link.getAttribute("href");
      expect(href).not.toBeNull();
      expect(VERIFIED_ROUTES.has(href!)).toBe(true);
    }
    // Two of the three cards carry a link — the NCERT provenance card
    // has no verified destination and must remain link-less.
    expect(links).toHaveLength(2);
    expect(links.map((l) => l.getAttribute("href"))).toEqual([
      "/student/analytics",
      "/student/weekly-assessments",
    ]);
  });

  it("has no unsupported claims (no percentages, ratings, testimonials, logos)", () => {
    render(<HowItFitsTogether />);
    const body = document.body.textContent ?? "";
    // Guard against sneaking numeric claims into the trust copy.
    expect(body).not.toMatch(/\d+\s*%/);
    expect(body.toLowerCase()).not.toMatch(/\b(testimonial|rating|reviews)\b|trusted by/);
  });
});
