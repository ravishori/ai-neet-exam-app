import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("@/features/ai/api", () => ({
  aiApi: {
    getStudyPlan: () => Promise.reject(new Error("no plan")),
    generateStudyPlan: () => Promise.reject(new Error("planner down")),
  },
}));

import StudyPlanPage from "@/app/student/study-plan/page";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <StudyPlanPage />
    </QueryClientProvider>,
  );
}

describe("Study plan shell", () => {
  it("surfaces a role=alert Alert when the generate mutation rejects", async () => {
    renderPage();
    // Provide an exam date to enable the button.
    const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: "2026-05-05" } });
    const btn = screen.getByRole("button", { name: /Generate plan/i });
    fireEvent.click(btn);
    const alert = await screen.findByTestId("study-plan-generate-error");
    expect(alert).toHaveAttribute("role", "alert");
  });
});
