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
vi.mock("@/features/assessment/api", () => ({
  assessmentApi: {
    generatePractice: (...args: unknown[]) => generatePractice(...args),
    startAttempt: (...args: unknown[]) => startAttempt(...args),
  },
}));

const meState = {
  data: {
    first_name: "Test",
    roles: ["STUDENT"],
    email_verified: true,
  } as {
    first_name: string;
    roles: string[];
    email_verified: boolean;
  },
  isLoading: false,
};

vi.mock("@/features/auth/use-auth", () => ({
  useMe: () => meState,
}));

const queryDataByKey: Record<string, unknown> = {};

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual<typeof import("@tanstack/react-query")>("@tanstack/react-query");
  return {
    ...actual,
    useQuery: ({ queryKey }: { queryKey: unknown[] }) => {
      const key = Array.isArray(queryKey) ? queryKey.join(":") : String(queryKey);
      return { data: queryDataByKey[key], isLoading: false };
    },
  };
});

import StudentDashboardPage from "@/app/student/dashboard/page";
import { PRACTICE_NOW_HERO_TEST_ID } from "@/features/assessment/use-start-practice";
import { ApiError } from "@/lib/api-client";

function renderDashboard() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <StudentDashboardPage />
    </QueryClientProvider>,
  );
}

describe("dashboard Practice Now hero CTA", () => {
  beforeEach(() => {
    push.mockReset();
    generatePractice.mockReset();
    startAttempt.mockReset();
    meState.data.email_verified = true;
    for (const key of Object.keys(queryDataByKey)) delete queryDataByKey[key];
  });

  it("renders the hero Continue practice button", () => {
    renderDashboard();
    expect(screen.getByTestId(PRACTICE_NOW_HERO_TEST_ID)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue practice/i })).toBeEnabled();
  });

  it("click sends one practice generate then startAttempt and navigates", async () => {
    const user = userEvent.setup();
    generatePractice.mockResolvedValue({ id: "assess-1", question_count: 30 });
    startAttempt.mockResolvedValue({ id: "attempt-1" });

    renderDashboard();
    await user.click(screen.getByTestId(PRACTICE_NOW_HERO_TEST_ID));

    await waitFor(() => {
      expect(generatePractice).toHaveBeenCalledTimes(1);
      expect(generatePractice).toHaveBeenCalledWith({ scope_type: "FULL", question_count: 30 });
    });
    await waitFor(() => {
      expect(startAttempt).toHaveBeenCalledTimes(1);
      expect(startAttempt).toHaveBeenCalledWith("assess-1");
    });
    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/student/attempts/attempt-1");
    });
  });

  it("pending state disables the CTA to prevent duplicate submits", async () => {
    const user = userEvent.setup();
    let resolveGen!: (v: unknown) => void;
    generatePractice.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveGen = resolve;
        }),
    );

    renderDashboard();
    const btn = screen.getByTestId(PRACTICE_NOW_HERO_TEST_ID);
    await user.click(btn);
    expect(btn).toBeDisabled();
    await user.click(btn);
    expect(generatePractice).toHaveBeenCalledTimes(1);
    resolveGen({ id: "assess-1", question_count: 30 });
    startAttempt.mockResolvedValue({ id: "attempt-1" });
    await waitFor(() => expect(startAttempt).toHaveBeenCalled());
  });

  it("API failure shows existing error copy", async () => {
    const user = userEvent.setup();
    generatePractice.mockRejectedValue(new ApiError("None left", "NO_QUESTIONS_AVAILABLE", 422));

    renderDashboard();
    await user.click(screen.getByTestId(PRACTICE_NOW_HERO_TEST_ID));

    expect(await screen.findByRole("status")).toHaveTextContent(/None left/i);
    expect(push).not.toHaveBeenCalled();
  });

  it("demotes recommendation actions — no competing Practice now buttons", () => {
    queryDataByKey["learning:recommendations"] = [
      {
        concept_id: "c1",
        concept_name: "Kinematic Equations",
        reason: "new_concept",
        mastery_score: null,
        published_question_count: 10,
      },
    ];
    renderDashboard();
    expect(screen.queryByRole("button", { name: /^practice now$/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue practice/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^practice$/i })).toBeInTheDocument();
  });

  it("places email verification outside the hero as a status strip", () => {
    meState.data.email_verified = false;
    renderDashboard();
    expect(screen.getByText(/email not verified/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /verify your email/i })).toHaveAttribute(
      "href",
      "/verify-email",
    );
    expect(screen.queryByRole("button", { name: /continue practice/i })).toBeInTheDocument();
  });
});
