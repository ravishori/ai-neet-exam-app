import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const reviewQueue = vi.fn();
const createReviewSession = vi.fn();
vi.mock("@/features/cms/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/cms/api")>("@/features/cms/api");
  return {
    ...actual,
    cmsApi: {
      reviewQueue: (...args: unknown[]) => reviewQueue(...args),
      createReviewSession: (...args: unknown[]) => createReviewSession(...args),
    },
  };
});

const subjects = vi.fn();
const chapters = vi.fn();
const topics = vi.fn();
vi.mock("@/features/academic/api", () => ({
  academicApi: {
    subjects: (...args: unknown[]) => subjects(...args),
    chapters: (...args: unknown[]) => chapters(...args),
    topics: (...args: unknown[]) => topics(...args),
  },
}));

import ReviewQueuePage from "@/app/admin/content/review-queue/page";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReviewQueuePage />
    </QueryClientProvider>,
  );
}

const ROW = {
  id: "q1",
  title: "Drift velocity question",
  status: "IN_REVIEW",
  academic: {
    subject: { id: "s1", name: "Physics" },
    chapter: { id: "c1", name: "Current Electricity", class_level: "12" },
    topic: { id: "t1", name: "Ohm's Law" },
    concept: { id: "cc1", name: "Drift Velocity" },
    class_level: "12",
  },
  batch_id: "b1",
  is_trusted_factory: true,
  risk_bucket: "GREEN" as const,
  risk_reasons: ["NCERT evidence verified"],
  created_at: "2026-01-01T00:00:00Z",
};

describe("Review Queue page (HR-2)", () => {
  beforeEach(() => {
    push.mockReset();
    reviewQueue.mockReset();
    createReviewSession.mockReset();
    subjects.mockReset();
    chapters.mockReset();
    topics.mockReset();
    subjects.mockResolvedValue([{ id: "s1", exam_id: "e", code: "PHY", name: "Physics", display_order: 1 }]);
    chapters.mockResolvedValue([]);
    topics.mockResolvedValue([]);
    reviewQueue.mockResolvedValue({
      data: [ROW],
      meta: {
        total: 1,
        limit: 25,
        offset: 0,
        risk_bucket: null,
        ordering: "created_at ASC, id ASC (stable)",
        risk_filter_scan_cap: null,
        no_llm_used_for_risk: true,
        no_auto_approve: true,
        no_auto_publish: true,
      },
    });
  });

  it("renders the queue with total count and trusted-factory indicator", async () => {
    renderPage();
    expect(await screen.findByText("Drift velocity question")).toBeInTheDocument();
    expect(screen.getByTestId("review-queue-total")).toHaveTextContent("Total 1");
    expect(screen.getByTestId("review-queue-trusted-count")).toHaveTextContent("1/1");
  });

  it("shows loading state then content", async () => {
    renderPage();
    expect(screen.queryByTestId("review-queue-loading")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId("review-queue-loading")).not.toBeInTheDocument());
  });

  it("shows error state", async () => {
    reviewQueue.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByTestId("review-queue-error")).toBeInTheDocument();
  });

  it("shows empty state when queue returns no rows", async () => {
    reviewQueue.mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 25, offset: 0, risk_bucket: null, ordering: "", risk_filter_scan_cap: null, no_llm_used_for_risk: true, no_auto_approve: true, no_auto_publish: true },
    });
    renderPage();
    expect(await screen.findByText("Nothing in this queue")).toBeInTheDocument();
  });

  it("applies subject filter and re-queries", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Drift velocity question");
    const subjectSelect = screen.getByTestId("review-queue-subject-filter");
    await waitFor(() => expect(within(subjectSelect).getByRole("option", { name: "Physics" })).toBeInTheDocument());
    await user.selectOptions(subjectSelect, "s1");
    await waitFor(() =>
      expect(reviewQueue).toHaveBeenCalledWith(expect.objectContaining({ subject_id: "s1" })),
    );
  });

  it("applies risk bucket filter", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Drift velocity question");
    await user.selectOptions(screen.getByTestId("review-queue-risk-filter"), "GREEN");
    await waitFor(() =>
      expect(reviewQueue).toHaveBeenCalledWith(expect.objectContaining({ risk_bucket: "GREEN" })),
    );
  });

  it("paginates via Next/Previous", async () => {
    reviewQueue.mockResolvedValue({
      data: [ROW],
      meta: { total: 60, limit: 25, offset: 0, risk_bucket: null, ordering: "", risk_filter_scan_cap: null, no_llm_used_for_risk: true, no_auto_approve: true, no_auto_publish: true },
    });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Drift velocity question");
    const next = screen.getByRole("button", { name: "Next" });
    expect(next).not.toBeDisabled();
    await user.click(next);
    await waitFor(() => expect(reviewQueue).toHaveBeenCalledWith(expect.objectContaining({ offset: 25 })));
  });

  it("starts a review session and navigates to it", async () => {
    createReviewSession.mockResolvedValue({ id: "sess-1" });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Drift velocity question");
    await user.click(screen.getByTestId("start-review-session"));
    await waitFor(() => expect(createReviewSession).toHaveBeenCalledWith(expect.objectContaining({ session_size: 25 })));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/admin/content/review-queue/session/sess-1"));
  });

  it("shows an error and does not navigate if session creation fails", async () => {
    createReviewSession.mockRejectedValue(new Error("no eligible items"));
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Drift velocity question");
    await user.click(screen.getByTestId("start-review-session"));
    await waitFor(() => expect(screen.getByText(/no eligible items|Failed to start review session/i)).toBeInTheDocument());
    expect(push).not.toHaveBeenCalled();
  });
});
