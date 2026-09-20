import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const generateMock = vi.fn();
const startAttempt = vi.fn();
vi.mock("@/features/assessment/api", () => ({
  assessmentApi: {
    generateMock: (...args: unknown[]) => generateMock(...args),
    startAttempt: (...args: unknown[]) => startAttempt(...args),
  },
}));

vi.mock("@/components/scope-picker", () => ({
  ScopePicker: () => <div data-testid="scope-picker" />,
}));

import MockTestsPage from "@/app/student/mock-tests/page";
import { MOCK_TEST_START_TEST_ID } from "@/features/assessment/use-start-practice";
import { ApiError } from "@/lib/api-client";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MockTestsPage />
    </QueryClientProvider>,
  );
}

describe("Mock tests page — start CTA", () => {
  beforeEach(() => {
    push.mockReset();
    generateMock.mockReset();
    startAttempt.mockReset();
  });

  it("click generates a mock (FULL scope by default), starts the attempt, and navigates", async () => {
    const user = userEvent.setup();
    generateMock.mockResolvedValue({ id: "mock-1" });
    startAttempt.mockResolvedValue({ id: "attempt-1" });

    renderPage();
    await user.click(screen.getByTestId(MOCK_TEST_START_TEST_ID));

    await waitFor(() => {
      expect(generateMock).toHaveBeenCalledWith({ scope_type: "FULL" });
      expect(startAttempt).toHaveBeenCalledWith("mock-1");
      expect(push).toHaveBeenCalledWith("/student/attempts/attempt-1");
    });
  });

  it("Start CTA disables and marks aria-busy while pending", async () => {
    const user = userEvent.setup();
    let resolveGen!: (v: unknown) => void;
    generateMock.mockImplementation(
      () => new Promise((resolve) => (resolveGen = resolve)),
    );

    renderPage();
    const btn = screen.getByTestId(MOCK_TEST_START_TEST_ID);
    await user.click(btn);
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
    await user.click(btn);
    expect(generateMock).toHaveBeenCalledTimes(1);
    resolveGen({ id: "mock-1" });
    startAttempt.mockResolvedValue({ id: "attempt-1" });
    await waitFor(() => expect(push).toHaveBeenCalled());
  });

  it("NO_QUESTIONS_AVAILABLE surfaces the destructive alert with fallback links", async () => {
    const user = userEvent.setup();
    generateMock.mockRejectedValue(
      new ApiError("Not enough published questions", "NO_QUESTIONS_AVAILABLE", 422),
    );

    renderPage();
    await user.click(screen.getByTestId(MOCK_TEST_START_TEST_ID));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Not enough published questions/i);
    expect(screen.getByRole("link", { name: /Try practice instead/i })).toBeInTheDocument();
    expect(startAttempt).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });
});
