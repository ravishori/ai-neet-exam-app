import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const generatePractice = vi.fn();
const startAttempt = vi.fn();
const listAttempts = vi.fn();
vi.mock("@/features/assessment/api", () => ({
  assessmentApi: {
    generatePractice: (...args: unknown[]) => generatePractice(...args),
    startAttempt: (...args: unknown[]) => startAttempt(...args),
    listAttempts: (...args: unknown[]) => listAttempts(...args),
  },
}));

const recommendations = vi.fn();
vi.mock("@/features/learning/api", () => ({
  learningApi: {
    recommendations: (...args: unknown[]) => recommendations(...args),
  },
}));

vi.mock("@/features/academic/api", () => ({
  academicApi: {
    subjects: () => Promise.resolve([]),
    chapters: () => Promise.resolve([]),
    topics: () => Promise.resolve([]),
    concepts: () => Promise.resolve([]),
  },
}));

import PracticePage from "@/app/student/practice/page";
import { PRACTICE_ARENA_START_TEST_ID } from "@/features/assessment/use-start-practice";
import { ApiError } from "@/lib/api-client";

function renderPractice() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <PracticePage />
    </QueryClientProvider>,
  );
}

describe("PREMIUM-004 practice arena", () => {
  beforeEach(() => {
    push.mockReset();
    generatePractice.mockReset();
    startAttempt.mockReset();
    listAttempts.mockReset();
    recommendations.mockReset();
    listAttempts.mockResolvedValue([]);
    recommendations.mockResolvedValue([]);
  });

  it("renders a single dominant Start practice CTA", async () => {
    renderPractice();
    expect(await screen.findByTestId(PRACTICE_ARENA_START_TEST_ID)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start practice/i })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /enter practice arena/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^practice now$/i })).not.toBeInTheDocument();
  });

  it("primary start uses FULL×30 when no scope is selected", async () => {
    const user = userEvent.setup();
    generatePractice.mockResolvedValue({ id: "assess-1", question_count: 30 });
    startAttempt.mockResolvedValue({ id: "attempt-1" });

    renderPractice();
    await user.click(await screen.findByTestId(PRACTICE_ARENA_START_TEST_ID));

    await waitFor(() => {
      expect(generatePractice).toHaveBeenCalledTimes(1);
      expect(generatePractice).toHaveBeenCalledWith({ scope_type: "FULL", question_count: 30 });
    });
    await waitFor(() => {
      expect(startAttempt).toHaveBeenCalledWith("assess-1");
    });
    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/student/attempts/attempt-1");
    });
  });

  it("surfaces recommendations with quiet Practice actions only", async () => {
    recommendations.mockResolvedValue([
      {
        concept_id: "c1",
        concept_name: "Projectile Motion",
        reason: "new_concept",
        mastery_score: null,
        published_question_count: 12,
      },
    ]);
    renderPractice();
    expect(await screen.findByText("Projectile Motion")).toBeInTheDocument();
    expect(screen.getByText(/not started yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^practice now$/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^practice$/i })).toBeInTheDocument();
  });

  it("shows honest empty suggestions state", async () => {
    recommendations.mockResolvedValue([]);
    renderPractice();
    expect(await screen.findByText(/no suggestions yet/i)).toBeInTheDocument();
  });

  it("links resume when an in-progress attempt exists", async () => {
    listAttempts.mockResolvedValue([
      {
        id: "att-open",
        assessment_id: "a1",
        status: "IN_PROGRESS",
        started_at: "2026-09-14T00:00:00Z",
        submitted_at: null,
        score: null,
        correct_count: null,
        incorrect_count: null,
        skipped_count: null,
      },
    ]);
    renderPractice();
    const resume = await screen.findByRole("link", { name: /resume session/i });
    expect(resume).toHaveAttribute("href", "/student/attempts/att-open");
  });

  it("preserves empty-pool error recovery actions", async () => {
    const user = userEvent.setup();
    generatePractice.mockRejectedValue(new ApiError("None left", "NO_QUESTIONS_AVAILABLE", 422));

    renderPractice();
    await user.click(await screen.findByTestId(PRACTICE_ARENA_START_TEST_ID));

    expect(await screen.findByRole("status")).toHaveTextContent(/None left/i);
    expect(screen.getByRole("button", { name: /practice any published question/i })).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });

  it("distinguishes untimed practice from timed mock without a competing filled CTA", async () => {
    renderPractice();
    expect(await screen.findByText(/untimed practice/i)).toBeInTheDocument();
    expect(screen.getByText(/timed mock/i)).toBeInTheDocument();
    const mockLink = screen.getByRole("link", { name: /open mock tests/i });
    expect(mockLink).toHaveAttribute("href", "/student/mock-tests");
    const filledStarts = screen.getAllByRole("button", { name: /start practice/i });
    expect(filledStarts).toHaveLength(1);
  });
});
