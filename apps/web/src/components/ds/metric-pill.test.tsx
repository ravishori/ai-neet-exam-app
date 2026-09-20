import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { MetricPill } from "@/components/ds/metric-pill";

describe("MetricPill (DS primitive)", () => {
  it("renders the uppercase label and monospaced value", () => {
    render(<MetricPill label="Accuracy" value="87%" />);
    const label = screen.getByText("Accuracy");
    const value = screen.getByText("87%");
    expect(label).toBeInTheDocument();
    expect(label.className).toMatch(/uppercase/);
    expect(value.className).toMatch(/font-mono/);
    expect(value.className).toMatch(/tabular-nums/);
  });

  it("merges caller className with the built-in token classes", () => {
    const { container } = render(<MetricPill label="Questions" value="12" className="w-40" />);
    const root = container.firstChild as HTMLElement;
    expect(root.className).toContain("w-40");
    expect(root.className).toContain("border-border/50");
  });
});
