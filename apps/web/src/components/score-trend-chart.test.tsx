import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScoreTrendChart } from "@/components/score-trend-chart";

describe("ScoreTrendChart", () => {
  it("shows a fallback message with fewer than 2 points", () => {
    render(<ScoreTrendChart points={[{ attemptId: "a1", label: "Jan 1", score: 80 }]} />);

    expect(screen.getByText(/Complete a few more assessments/)).toBeInTheDocument();
  });

  it("renders the chart and direct-labels the endpoint score", () => {
    render(
      <ScoreTrendChart
        points={[
          { attemptId: "a1", label: "Jan 1", score: 60 },
          { attemptId: "a2", label: "Jan 2", score: 85 },
        ]}
      />
    );

    expect(screen.getByRole("img", { name: /Accuracy trend/ })).toBeInTheDocument();
    expect(screen.getByText("85%")).toBeInTheDocument();
  });
});
