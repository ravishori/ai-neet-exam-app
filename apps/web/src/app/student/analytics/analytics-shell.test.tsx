import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("@/features/learning/api", () => ({
  learningApi: {
    overview: () => Promise.reject(new Error("overview down")),
  },
}));

vi.mock("@/features/assessment/api", () => ({
  assessmentApi: {
    listAttempts: () => Promise.reject(new Error("attempts down")),
  },
}));

import StudentAnalyticsPage from "@/app/student/analytics/page";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <StudentAnalyticsPage />
    </QueryClientProvider>,
  );
}

describe("Analytics shell", () => {
  it("surfaces a role=alert Alert when the subject overview query rejects", async () => {
    renderPage();
    const alert = await screen.findByTestId("analytics-overview-error");
    expect(alert).toHaveAttribute("role", "alert");
    expect(alert).toHaveTextContent(/Could not load subject data/i);
    expect(alert).toHaveTextContent(/Retry/i);
  });

  it("surfaces a role=alert Alert when the attempts query rejects", async () => {
    renderPage();
    const alert = await screen.findByTestId("analytics-attempts-error");
    expect(alert).toHaveAttribute("role", "alert");
    expect(alert).toHaveTextContent(/Could not load attempt history/i);
  });
});
