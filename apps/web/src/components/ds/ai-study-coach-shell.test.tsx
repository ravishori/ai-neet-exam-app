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
});
