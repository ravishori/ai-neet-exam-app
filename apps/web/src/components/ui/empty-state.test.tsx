import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EmptyState } from "@/components/ui/empty-state";

describe("EmptyState", () => {
  it("renders the title", () => {
    render(<EmptyState title="No questions found" />);
    expect(screen.getByText("No questions found")).toBeInTheDocument();
  });

  it("renders the description when provided", () => {
    render(<EmptyState title="No results" description="Try a different filter." />);
    expect(screen.getByText("Try a different filter.")).toBeInTheDocument();
  });

  it("omits the description paragraph when none is provided", () => {
    render(<EmptyState title="No results" />);
    expect(screen.queryByText("Try a different filter.")).not.toBeInTheDocument();
  });

  it("renders the action node", () => {
    render(<EmptyState title="No results" action={<button>Retry</button>} />);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
