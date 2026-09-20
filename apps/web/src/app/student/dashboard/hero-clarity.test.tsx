import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const meState = {
  data: { first_name: "Priya", roles: ["STUDENT"], email_verified: true },
  isLoading: false,
};
vi.mock("@/features/auth/use-auth", () => ({ useMe: () => meState }));

vi.mock("@/features/assessment/api", () => ({
  assessmentApi: {
    listAttempts: vi.fn(() => Promise.resolve([])),
    generatePractice: vi.fn(),
    startAttempt: vi.fn(),
  },
}));
vi.mock("@/features/learning/api", () => ({
  learningApi: {
    overview: vi.fn(() => Promise.resolve([])),
    revisionDue: vi.fn(() =>
      Promise.resolve([
        {
          concept_id: "c1",
          concept_name: "Kinematic Equations",
          mastery_score: 42,
          published_question_count: 12,
        },
      ]),
    ),
    recommendations: vi.fn(() => Promise.resolve([])),
  },
}));

import StudentDashboardPage from "@/app/student/dashboard/page";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <StudentDashboardPage />
    </QueryClientProvider>,
  );
}

describe("dashboard hero clarity", () => {
  beforeEach(() => push.mockReset());

  it("shows the session-shape caption under the primary CTA", () => {
    renderPage();
    const caption = screen.getByTestId("dashboard-hero-session-shape");
    expect(caption).toHaveTextContent(/30 published questions/i);
    expect(caption).toHaveTextContent(/untimed/i);
    expect(caption).toHaveTextContent(/full syllabus/i);
  });

  it("does not phrase the hero copy as if the CTA jumps to the focus concept", async () => {
    renderPage();
    // The Revision due card names the concept — that is where the student
    // actually opens it. The hero MUST tell the student that the concept
    // lives elsewhere, not that Continue practice targets it. Wait for
    // the mocked revision-due query to resolve before asserting copy.
    await waitFor(() => {
      expect(document.body.textContent ?? "").toMatch(/Kinematic Equations/);
    });
    expect(document.body.textContent ?? "").toMatch(
      /next concept to revise is Kinematic Equations/i,
    );
    // The old, misleading "Next focus: X. Continue practice…" phrasing
    // must not resurface.
    expect(document.body.textContent ?? "").not.toMatch(
      /Next focus: Kinematic Equations\. Continue practice/i,
    );
  });
});
