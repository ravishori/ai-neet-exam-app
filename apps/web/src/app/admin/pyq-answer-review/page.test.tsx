import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const counts = vi.fn();
const list = vi.fn();
vi.mock("@/features/pyq-answer-review/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/pyq-answer-review/api")>(
    "@/features/pyq-answer-review/api",
  );
  return {
    ...actual,
    pyqAnswerReviewApi: {
      counts: (...args: unknown[]) => counts(...args),
      list: (...args: unknown[]) => list(...args),
    },
  };
});

import PyqAnswerReviewQueuePage from "@/app/admin/pyq-answer-review/page";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PyqAnswerReviewQueuePage />
    </QueryClientProvider>,
  );
}

describe("PyqAnswerReviewQueuePage", () => {
  it("renders live counts and the eligible queue", async () => {
    counts.mockResolvedValue({
      eligible: 7720,
      requires_manual_review: 1,
      structurally_invalid: 1207,
      total_pending: 8928,
      reviewed_by_human: 3,
      skipped: 1,
    });
    list.mockResolvedValue({
      items: [
        {
          id: "q1",
          staging_id: "abc123",
          subject: "Physics",
          class_level: "12",
          exam_year: "2024",
          paper_code: "P1",
          stem_preview: "A charge q moves through...",
        },
      ],
      page: 1,
      page_size: 25,
      returned: 1,
    });

    renderPage();

    await waitFor(() => expect(screen.getByTestId("counts-summary")).toBeInTheDocument());
    expect(screen.getByText(/Eligible 7720/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("queue-list")).toBeInTheDocument());
    expect(screen.getByText(/A charge q moves through/)).toBeInTheDocument();
  });

  it("shows an empty state when nothing is eligible", async () => {
    counts.mockResolvedValue({
      eligible: 0,
      requires_manual_review: 0,
      structurally_invalid: 0,
      total_pending: 0,
      reviewed_by_human: 0,
      skipped: 0,
    });
    list.mockResolvedValue({ items: [], page: 1, page_size: 25, returned: 0 });

    renderPage();

    await waitFor(() => expect(screen.getByText(/Nothing in this queue/)).toBeInTheDocument());
  });
});
