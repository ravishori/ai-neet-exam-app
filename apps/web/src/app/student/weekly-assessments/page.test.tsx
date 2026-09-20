import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { apiClient } from "@/lib/api-client";
import WeeklyAssessmentsPage from "@/app/student/weekly-assessments/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <WeeklyAssessmentsPage />
    </QueryClientProvider>,
  );
}

const RECOMMENDATION_FIXTURE = {
  id: "rec-1",
  iso_year: 2026,
  iso_week: 38,
  status: "RECOMMENDED" as const,
  estimated_duration_minutes: 60,
  marks_per_question: 4,
  negative_marks_per_question: 1,
  attempt_limit: 1,
  total_questions: 60,
  generated_at: new Date().toISOString(),
  blueprint: [
    {
      label: "Physics",
      quota: 15,
      recent_quota: 11,
      previous_quota: 4,
      recent_chapter_count: 3,
      previous_chapter_count: 2,
      weak_chapter_count: 1,
      used_cold_start: false,
    },
    {
      label: "Chemistry",
      quota: 15,
      recent_quota: 11,
      previous_quota: 4,
      recent_chapter_count: 2,
      previous_chapter_count: 1,
      weak_chapter_count: 0,
      used_cold_start: false,
    },
    {
      label: "Biology",
      quota: 30,
      recent_quota: 23,
      previous_quota: 7,
      recent_chapter_count: 4,
      previous_chapter_count: 3,
      weak_chapter_count: 2,
      used_cold_start: false,
    },
  ],
  reason: { cold_start: false, buckets: [] },
};

describe("Weekly Revision page (student MVP)", () => {
  beforeEach(() => {
    // Emulate 375px mobile viewport
    Object.defineProperty(window, "innerWidth", { value: 375, configurable: true });
    Object.defineProperty(window, "innerHeight", { value: 812, configurable: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the recommendation card + start CTA at 375px", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(RECOMMENDATION_FIXTURE as never);
    renderPage();

    expect(await screen.findByText(/Your Weekly Revision Assessment/i)).toBeInTheDocument();
    expect(await screen.findByText(/Week 38.*Recommended for you/i)).toBeInTheDocument();
    expect(screen.getByText(/60 questions/i)).toBeInTheDocument();
    expect(screen.getByText(/60 min · \+4 \/ -1/i)).toBeInTheDocument();

    // Non-blocking reminder copy
    expect(screen.getByText(/Recommended, not required/i)).toBeInTheDocument();

    const cta = screen.getByTestId("weekly-revision-start");
    expect(cta).toBeEnabled();
    expect(cta).not.toHaveAttribute("aria-disabled", "true");
  });

  it("shows the UNAVAILABLE state without a start CTA", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({
      ...RECOMMENDATION_FIXTURE,
      status: "UNAVAILABLE",
      blueprint: [],
      reason: {
        cold_start: false,
        buckets: [],
        unavailable_reasons: ["Physics: only 5 published questions available, need 15"],
      },
    } as never);
    renderPage();

    expect(await screen.findByText(/Not enough questions yet/i)).toBeInTheDocument();
    expect(screen.getByText(/Physics: only 5 published questions/i)).toBeInTheDocument();
    expect(screen.queryByTestId("weekly-revision-start")).not.toBeInTheDocument();
  });

  it("renders COMPLETED state with the CTA disabled", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({
      ...RECOMMENDATION_FIXTURE,
      status: "COMPLETED",
    } as never);
    renderPage();

    const cta = await screen.findByTestId("weekly-revision-start");
    expect(cta).toBeDisabled();
    expect(cta).toHaveAttribute("aria-disabled", "true");
    expect(cta).toHaveTextContent(/Completed for this week/i);
  });

  it("renders IN_PROGRESS state with a Resume CTA that is enabled", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({
      ...RECOMMENDATION_FIXTURE,
      status: "IN_PROGRESS",
    } as never);
    renderPage();

    const cta = await screen.findByTestId("weekly-revision-start");
    expect(cta).toBeEnabled();
    expect(cta).toHaveTextContent(/Resume assessment/i);
  });

  it("surfaces load errors as an accessible alert", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("boom"));
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Could not load this week/i);
  });
});
