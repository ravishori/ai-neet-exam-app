import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AnswerOption } from "@/components/ds/answer-option";

describe("AnswerOption", () => {
  it("renders default state and calls onSelect", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <AnswerOption label="1" letter="A" text="Newton's first law" state="default" onSelect={onSelect} />,
    );
    const btn = screen.getByRole("button", { name: /Option 1:/i });
    expect(btn).toHaveAttribute("data-state", "default");
    await user.click(btn);
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("marks selected with aria-pressed", () => {
    render(<AnswerOption label="1" letter="A" text="Selected" state="selected" onSelect={() => {}} />);
    expect(screen.getByRole("button", { name: /Option 1:/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button")).toHaveAttribute("data-state", "selected");
  });

  it("shows check for correct and x for incorrect", () => {
    const { rerender } = render(
      <AnswerOption label="1" letter="A" text="Right" state="correct" onSelect={() => {}} />,
    );
    expect(screen.getByRole("button")).toHaveAttribute("data-state", "correct");
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "false");
    rerender(<AnswerOption label="1" letter="A" text="Wrong" state="incorrect" onSelect={() => {}} />);
    expect(screen.getByRole("button")).toHaveAttribute("data-state", "incorrect");
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button")).toHaveAttribute("aria-invalid", "true");
  });

  it("does not fire when disabled", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <AnswerOption label="1" letter="A" text="Locked" state="default" disabled onSelect={onSelect} />,
    );
    await user.click(screen.getByRole("button"));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
