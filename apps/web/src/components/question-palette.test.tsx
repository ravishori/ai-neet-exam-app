import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { QuestionPalette } from "@/components/question-palette";

describe("PREMIUM-005 QuestionPalette", () => {
  it("exposes answered/current states and jumps without changing semantics", async () => {
    const user = userEvent.setup();
    const onJump = vi.fn();
    render(
      <QuestionPalette
        currentIndex={0}
        onJump={onJump}
        statuses={[
          { answered: true, markedForReview: false, visited: true },
          { answered: false, markedForReview: true, visited: true },
          { answered: false, markedForReview: false, visited: false },
        ]}
      />,
    );
    const q2 = screen.getByRole("button", { name: /Question 2, not answered, marked for review/i });
    expect(q2.className).toMatch(/min-h-11/);
    await user.click(q2);
    expect(onJump).toHaveBeenCalledWith(1);
  });
});
