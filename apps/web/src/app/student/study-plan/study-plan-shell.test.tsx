import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const generateStudyPlan = vi.fn();

vi.mock("@/features/ai/api", () => ({
  aiApi: {
    getStudyPlan: () => Promise.reject(new Error("no plan")),
    generateStudyPlan: (...args: unknown[]) => generateStudyPlan(...args),
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

function fillDateAndSubmit() {
  const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
  fireEvent.change(dateInput, { target: { value: "2026-05-05" } });
  fireEvent.click(screen.getByRole("button", { name: /Generate plan/i }));
}

const BASE_PLAN = {
  id: "plan-1",
  target_score: 650,
  current_score: 450,
  exam_date: "2026-05-05",
  hours_per_day: 6,
  plan: { summary: "Test plan", weekly_focus: ["Focus one"], daily_schedule: [{ day: 1, focus: "Day one", duration_minutes: 180 }] },
};

describe("Study plan shell", () => {
  it("surfaces a role=alert Alert when the generate mutation rejects", async () => {
    generateStudyPlan.mockRejectedValueOnce(new Error("planner down"));
    renderPage();
    fillDateAndSubmit();
    const alert = await screen.findByTestId("study-plan-generate-error");
    expect(alert).toHaveAttribute("role", "alert");
  });

  it("labels a deterministic fallback plan as a Standard plan, not AI-personalized", async () => {
    generateStudyPlan.mockResolvedValueOnce({ ...BASE_PLAN, is_fallback: true });
    renderPage();
    fillDateAndSubmit();

    await waitFor(() => expect(screen.getByText("Standard plan")).toBeInTheDocument());
    expect(screen.queryByText("AI-personalized")).not.toBeInTheDocument();
    expect(screen.getByText(/AI personalization wasn't available for this request/i)).toBeInTheDocument();
  });

  it("labels a successful AI-personalized plan accordingly", async () => {
    generateStudyPlan.mockResolvedValueOnce({ ...BASE_PLAN, is_fallback: false });
    renderPage();
    fillDateAndSubmit();

    await waitFor(() => expect(screen.getByText("AI-personalized")).toBeInTheDocument());
    expect(screen.queryByText("Standard plan")).not.toBeInTheDocument();
    expect(screen.getByText(/not a certified NEET prep plan/i)).toBeInTheDocument();
  });
});
