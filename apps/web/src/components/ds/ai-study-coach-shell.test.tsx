import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/student/dashboard" }));
vi.mock("@/components/concept-picker", () => ({
  ConceptPicker: () => <div data-testid="concept-picker" />,
}));
vi.mock("@/components/ai-tutor-box", () => ({
  AiTutorBox: () => <div data-testid="tutor-box" />,
}));

import { AiStudyCoachShell } from "@/components/ds/ai-study-coach-shell";

function renderShell() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AiStudyCoachShell />
    </QueryClientProvider>,
  );
}

describe("AI Study Coach shell", () => {
  it("opens a dialog with aria-modal and closes on Escape", () => {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: /Open AI Study Coach/i }));
    const dialog = screen.getByTestId("study-coach-dialog");
    expect(dialog).toHaveAttribute("role", "dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByTestId("study-coach-dialog")).toBeNull();
  });

  it("moves initial focus into the dialog and wraps Tab focus at the edges", () => {
    renderShell();
    const launcher = screen.getByRole("button", { name: /Open AI Study Coach/i });
    fireEvent.click(launcher);

    // Initial focus should be inside the dialog, not on the launcher.
    expect(document.activeElement).not.toBe(launcher);
    const dialogRoot = screen.getByTestId("study-coach-dialog").parentElement!;
    expect(dialogRoot.contains(document.activeElement)).toBe(true);

    const tabbables = dialogRoot.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    const first = tabbables[0];
    const last = tabbables[tabbables.length - 1];

    // Shift+Tab from the first tabbable wraps to the last.
    first.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);

    // Tab from the last tabbable wraps to the first.
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);
  });
});
