import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useParams: () => ({ attemptId: "attempt-1" }),
}));

const getAttempt = vi.fn();
const saveAnswer = vi.fn();
const submitAttempt = vi.fn();
vi.mock("@/features/assessment/api", () => ({
  assessmentApi: {
    getAttempt: (...args: unknown[]) => getAttempt(...args),
    saveAnswer: (...args: unknown[]) => saveAnswer(...args),
    submitAttempt: (...args: unknown[]) => submitAttempt(...args),
    questionHistory: () => Promise.resolve([]),
  },
}));

vi.mock("@/features/learning/api", () => ({
  learningApi: {
    toggleBookmark: () => Promise.resolve({ bookmarked: true }),
    getNote: () => Promise.resolve({ note_text: null }),
    upsertNote: () => Promise.resolve({ note_text: "" }),
  },
}));

vi.mock("@/features/questions/api", () => ({
  questionsApi: {
    related: () => Promise.resolve([]),
    report: () => Promise.resolve({}),
  },
}));

import AttemptRunnerPage from "@/app/student/attempts/[attemptId]/page";

function named(id: string, name: string) {
  return { id, name };
}

function makeAttempt(overrides: Record<string, unknown> = {}) {
  return {
    id: "attempt-1",
    assessment_id: "assess-1",
    status: "IN_PROGRESS",
    started_at: "2026-09-14T10:00:00.000Z",
    submitted_at: null,
    score: null,
    correct_count: null,
    incorrect_count: null,
    skipped_count: null,
    assessment: {
      id: "assess-1",
      assessment_type: "PRACTICE",
      scope_type: "FULL",
      scope_id: null,
      title: "Practice · Full syllabus",
      duration_minutes: null,
      marks_per_question: 4,
      negative_marks_per_question: 0,
      question_count: 2,
    },
    questions: [
      {
        content_item_id: "q1",
        stem: "What is instantaneous velocity?",
        options: [
          { label: "1", text: "Displacement over time" },
          { label: "2", text: "Speed at an instant" },
          { label: "3", text: "Average speed only" },
          { label: "4", text: "Acceleration times time" },
        ],
        selected_option: null,
        confidence: null,
        marked_for_review: false,
        bookmarked: false,
        question_type: "MCQ",
        difficulty: "medium",
        pyq_year: null,
        images: [],
        subject: named("s1", "Physics"),
        chapter: named("c1", "Motion"),
        topic: named("t1", "Kinematics"),
        concept: named("k1", "Velocity"),
        ncert_reference: null,
      },
      {
        content_item_id: "q2",
        stem: "Second question stem",
        options: [
          { label: "1", text: "A" },
          { label: "2", text: "B" },
          { label: "3", text: "C" },
          { label: "4", text: "D" },
        ],
        selected_option: "2",
        confidence: null,
        marked_for_review: false,
        bookmarked: false,
        question_type: "MCQ",
        difficulty: "easy",
        pyq_year: null,
        images: [],
        subject: named("s1", "Physics"),
        chapter: named("c1", "Motion"),
        topic: named("t1", "Kinematics"),
        concept: named("k2", "Acceleration"),
        ncert_reference: null,
      },
    ],
    ...overrides,
  };
}

function renderRunner() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AttemptRunnerPage />
    </QueryClientProvider>,
  );
}

describe("PREMIUM-005 practice runner", () => {
  beforeEach(() => {
    push.mockReset();
    getAttempt.mockReset();
    saveAnswer.mockReset();
    submitAttempt.mockReset();
    getAttempt.mockResolvedValue(makeAttempt());
    saveAnswer.mockResolvedValue({});
  });

  it("renders focused runner shell with stem and progress", async () => {
    renderRunner();
    expect(await screen.findByTestId("practice-runner")).toBeInTheDocument();
    expect(screen.getByTestId("practice-runner-stem")).toHaveTextContent(/instantaneous velocity/i);
    expect(screen.getByTestId("practice-runner-progress")).toHaveTextContent("1");
    expect(screen.getByTestId("practice-runner-progress")).toHaveTextContent("2");
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("makes Save & Next the primary forward action before the last question", async () => {
    renderRunner();
    await screen.findByTestId("practice-runner");
    const next = screen.getByTestId("practice-runner-next");
    expect(next).toHaveTextContent(/save & next/i);
    expect(next.className).toMatch(/font-semibold/);
    const submits = screen.getAllByRole("button", { name: /^submit$/i });
    expect(submits.length).toBeGreaterThan(0);
    expect(submits.every((el) => /text-muted-foreground|ghost/i.test(el.className))).toBe(true);
  });

  it("selects an option without changing option labels or order", async () => {
    const user = userEvent.setup();
    renderRunner();
    await screen.findByTestId("practice-runner-stem");
    const options = screen.getAllByRole("button", { name: /Option \d:/i });
    expect(options).toHaveLength(4);
    expect(options[0]).toHaveAccessibleName(/Option 1: Displacement over time/i);
    expect(options[1]).toHaveAccessibleName(/Option 2: Speed at an instant/i);
    await user.click(options[1]);
    // The runner autosave is debounced (see 0349b5b) — wait for the
    // trailing flush before asserting the mutation payload.
    await waitFor(() =>
      expect(saveAnswer).toHaveBeenCalledWith(
        "attempt-1",
        expect.objectContaining({ content_item_id: "q1", selected_option: "2" }),
      ),
    );
  });

  it("navigates with palette jump semantics preserved", async () => {
    const user = userEvent.setup();
    renderRunner();
    await screen.findByTestId("practice-runner");
    const palettes = screen.getAllByRole("navigation", { name: /question palette/i });
    const jump = within(palettes[0]).getByRole("button", { name: /Question 2/i });
    await user.click(jump);
    expect(await screen.findByTestId("practice-runner-stem")).toHaveTextContent(/second question stem/i);
  });

  it("does not invent a timer when duration_minutes is null", async () => {
    renderRunner();
    await screen.findByTestId("practice-runner");
    expect(screen.queryByTestId("practice-runner-timer")).not.toBeInTheDocument();
  });

  it("shows timer presentation when duration_minutes is present", async () => {
    getAttempt.mockResolvedValue(
      makeAttempt({
        assessment: {
          id: "assess-1",
          assessment_type: "MOCK",
          scope_type: "FULL",
          scope_id: null,
          title: "Mock · Full",
          duration_minutes: 180,
          marks_per_question: 4,
          negative_marks_per_question: 1,
          question_count: 2,
        },
      }),
    );
    renderRunner();
    expect(await screen.findByTestId("practice-runner-timer")).toBeInTheDocument();
    expect(screen.getByRole("timer")).toBeInTheDocument();
  });
});
