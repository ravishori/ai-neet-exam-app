import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const meState = {
  data: { first_name: "Test", roles: ["STUDENT"], email_verified: true } as {
    first_name: string; roles: string[]; email_verified: boolean;
  },
  isLoading: false,
};
vi.mock("@/features/auth/use-auth", () => ({ useMe: () => meState }));

vi.mock("@/features/assessment/api", () => ({
  assessmentApi: {
    listAttempts: vi.fn(() => Promise.reject(new Error("attempts down"))),
  },
}));
vi.mock("@/features/learning/api", () => ({
  learningApi: {
    overview: vi.fn(() => Promise.reject(new Error("overview down"))),
    revisionDue: vi.fn(() => Promise.reject(new Error("revision down"))),
    recommendations: vi.fn(() => Promise.reject(new Error("recs down"))),
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

describe("dashboard section fetch errors", () => {
  beforeEach(() => {
    push.mockReset();
  });

  it("renders all four inline error alerts with retry buttons when each API rejects", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("dashboard-revision-error")).toBeInTheDocument();
      expect(screen.getByTestId("dashboard-recommendations-error")).toBeInTheDocument();
      expect(screen.getByTestId("dashboard-overview-error")).toBeInTheDocument();
      expect(screen.getByTestId("dashboard-attempts-error")).toBeInTheDocument();
    });
    const alerts = screen.getAllByRole("alert");
    // At least four (may include the HeroPracticeCta alert if the query
    // fires — accept a lower bound so this test stays resilient to
    // unrelated CTA state).
    expect(alerts.length).toBeGreaterThanOrEqual(4);
    // Every section alert exposes a "Retry" button.
    for (const testid of [
      "dashboard-revision-error",
      "dashboard-recommendations-error",
      "dashboard-overview-error",
      "dashboard-attempts-error",
    ]) {
      const alert = screen.getByTestId(testid);
      const retry = alert.querySelector("button");
      expect(retry).not.toBeNull();
      await userEvent.click(retry!);
    }
  });
});
