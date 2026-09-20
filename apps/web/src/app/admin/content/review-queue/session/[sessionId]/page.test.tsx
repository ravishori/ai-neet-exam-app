import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useParams: () => ({ sessionId: "sess-1" }),
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const getReviewSession = vi.fn();
const advanceReviewSession = vi.fn();
const claimReviewItem = vi.fn();
const reviewPacket = vi.fn();
const review = vi.fn();

vi.mock("@/features/cms/api", () => ({
  cmsApi: {
    getReviewSession: (...args: unknown[]) => getReviewSession(...args),
    advanceReviewSession: (...args: unknown[]) => advanceReviewSession(...args),
    claimReviewItem: (...args: unknown[]) => claimReviewItem(...args),
    reviewPacket: (...args: unknown[]) => reviewPacket(...args),
    review: (...args: unknown[]) => review(...args),
  },
}));

import ReviewSessionPage from "@/app/admin/content/review-queue/session/[sessionId]/page";
import { ApiError } from "@/lib/api-client";

function baseSession(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "sess-1",
    reviewer_id: "u1",
    session_size: 2,
    item_ids: ["q1", "q2"],
    position: 0,
    status: "ACTIVE",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    current_item_id: "q1",
    remaining: 2,
    ...overrides,
  };
}

function basePacket(id: string) {
  return {
    item_id: id,
    title: `Question ${id}`,
    content_type: "QUESTION",
    status: "IN_REVIEW",
    language: "en",
    tags: [],
    concept_id: "concept-1",
    academic: {
      subject: { id: "s1", name: "Physics" },
      chapter: { id: "c1", name: "Current Electricity" },
      topic: { id: "t1", name: "Ohm's Law" },
      concept: { id: "cc1", name: "Drift Velocity" },
    },
    question: {
      stem: `Stem for ${id}`,
      options: [
        { label: "A", text: "Alpha" },
        { label: "B", text: "Beta" },
        { label: "C", text: "Gamma" },
        { label: "D", text: "Delta" },
      ],
      correct_option: "A",
      explanation: "Because alpha is correct.",
      difficulty: "medium",
    },
    body: {
      ncert_evidence: {
        verification_level: "SECTION_VERIFIED",
        source_document: "NCERT Class XII Physics",
        chapter: "Current Electricity",
        section: "3.4",
      },
    },
    provenance: { model_used: "mock-claude", has_lineage: true, status: "known" },
    structural: { valid: true, issues: [], review_ready: true },
    suspected_duplicates: [],
    reviews: [],
    ai_assistance: { report: null, disclaimer: "" },
    factory_qa: { present: false, disclaimer: "", blueprint_id: null },
    checklist: [],
    chapter_inventory: null,
    campaign_notes: {},
    publication_eligibility: {},
  };
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ReviewSessionPage />
    </QueryClientProvider>,
  );
}

describe("Review Session workspace (HR-2)", () => {
  beforeEach(() => {
    getReviewSession.mockReset();
    advanceReviewSession.mockReset();
    claimReviewItem.mockReset();
    reviewPacket.mockReset();
    review.mockReset();

    getReviewSession.mockResolvedValue(baseSession());
    claimReviewItem.mockResolvedValue({ id: "claim-1", status: "ACTIVE" });
    reviewPacket.mockImplementation((id: string) => Promise.resolve(basePacket(id)));
  });

  it("shows loading then the question stem, options, explanation, and NCERT evidence", async () => {
    renderPage();
    expect(screen.getByTestId("session-loading")).toBeInTheDocument();
    expect(await screen.findByTestId("question-stem")).toHaveTextContent("Stem for q1");
    expect(screen.getByTestId("question-options")).toHaveTextContent("Alpha");
    expect(screen.getByTestId("question-explanation")).toHaveTextContent("Because alpha is correct.");
    expect(screen.getByTestId("ncert-evidence")).toHaveTextContent("SECTION_VERIFIED");
  });

  it("shows session error state", async () => {
    getReviewSession.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByTestId("session-error")).toBeInTheDocument();
  });

  it("navigates Next/Previous within the session without mutating server position", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByTestId("question-stem")).toHaveTextContent("Stem for q2");
    expect(screen.getByTestId("readonly-preview-banner")).toBeInTheDocument();
    expect(advanceReviewSession).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Previous" }));
    expect(await screen.findByTestId("question-stem")).toHaveTextContent("Stem for q1");
    expect(screen.queryByTestId("readonly-preview-banner")).not.toBeInTheDocument();
  });

  it("approve calls the review endpoint then advances, only after server success", async () => {
    review.mockResolvedValue({ id: "q1", status: "APPROVED" });
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-approve"));
    await waitFor(() => expect(review).toHaveBeenCalledWith("q1", { decision: "approve" }));
    await waitFor(() => expect(advanceReviewSession).toHaveBeenCalledWith("sess-1"));
    await waitFor(() => expect(screen.getByTestId("question-stem")).toHaveTextContent("Stem for q2"));
  });

  it("failed approve shows an error and does not advance", async () => {
    review.mockRejectedValue(new ApiError("Gate failed", "PUBLICATION_GATES_NOT_MET", 422));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-approve"));
    expect(await screen.findByTestId("action-error")).toHaveTextContent("Gate failed");
    expect(advanceReviewSession).not.toHaveBeenCalled();
    expect(screen.getByTestId("question-stem")).toHaveTextContent("Stem for q1");
  });

  it("changes-requested requires a reason before submit is enabled", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-changes-requested"));
    const submit = await screen.findByTestId("submit-changes-requested");
    expect(submit).toBeDisabled();
    await user.selectOptions(screen.getByTestId("changes-reason-select"), "Incorrect answer");
    expect(submit).not.toBeDisabled();
  });

  it("changes-requested success sends structured reason and optional note, then advances", async () => {
    review.mockResolvedValue({ id: "q1", status: "CHANGES_REQUESTED" });
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-changes-requested"));
    await user.selectOptions(screen.getByTestId("changes-reason-select"), "Duplicate");
    await user.type(screen.getByTestId("changes-note"), "looks like q9");
    await user.click(screen.getByTestId("submit-changes-requested"));
    await waitFor(() =>
      expect(review).toHaveBeenCalledWith("q1", {
        decision: "request_changes",
        comment: "Reason: Duplicate. Note: looks like q9",
      }),
    );
    await waitFor(() => expect(advanceReviewSession).toHaveBeenCalled());
  });

  it("skip leaves content untouched (no review() call) and advances", async () => {
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-skip"));
    await waitFor(() => expect(advanceReviewSession).toHaveBeenCalledWith("sess-1"));
    expect(review).not.toHaveBeenCalled();
  });

  it("flag reports the gap without calling a mutation endpoint", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-flag"));
    expect(await screen.findByTestId("flag-notice")).toHaveTextContent(/not implemented/i);
    expect(review).not.toHaveBeenCalled();
    expect(advanceReviewSession).not.toHaveBeenCalled();
  });

  it("shows a claim-conflict warning but does not block actions (backend authoritative)", async () => {
    claimReviewItem.mockRejectedValue(new ApiError("already claimed", "ALREADY_CLAIMED", 409));
    renderPage();
    expect(await screen.findByTestId("claim-warning")).toHaveTextContent(/already claimed/i);
    expect(screen.getByTestId("action-approve")).not.toBeDisabled();
  });

  it("keyboard shortcut A approves the current item", async () => {
    review.mockResolvedValue({ id: "q1", status: "APPROVED" });
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.keyboard("a");
    await waitFor(() => expect(review).toHaveBeenCalledWith("q1", { decision: "approve" }));
  });

  it("keyboard shortcut S skips", async () => {
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.keyboard("s");
    await waitFor(() => expect(advanceReviewSession).toHaveBeenCalled());
  });

  it("keyboard shortcuts N/P navigate", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.keyboard("n");
    expect(await screen.findByTestId("question-stem")).toHaveTextContent("Stem for q2");
    await user.keyboard("p");
    expect(await screen.findByTestId("question-stem")).toHaveTextContent("Stem for q1");
  });

  it("keyboard shortcut C opens the Changes Requested dialog, Esc closes it", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.keyboard("c");
    expect(await screen.findByTestId("changes-reason-select")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByTestId("changes-reason-select")).not.toBeInTheDocument());
  });

  it("does not trigger shortcuts while typing in the reviewer note textarea", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-changes-requested"));
    const noteField = await screen.findByTestId("changes-note");
    await user.click(noteField);
    await user.type(noteField, "s a c f");
    expect(review).not.toHaveBeenCalled();
    expect(advanceReviewSession).not.toHaveBeenCalled();
    expect(screen.getByTestId("changes-reason-select")).toBeInTheDocument();
  });

  it("shows session-completed state", async () => {
    getReviewSession.mockResolvedValue(baseSession({ status: "COMPLETED", position: 2, remaining: 0 }));
    renderPage();
    expect(await screen.findByTestId("session-completed")).toBeInTheDocument();
  });

  it("action buttons are real <button> elements with accessible names", async () => {
    renderPage();
    await screen.findByTestId("question-stem");
    expect(screen.getByRole("button", { name: /Approve/i })).toBeInstanceOf(HTMLButtonElement);
    expect(screen.getByRole("button", { name: /Changes Requested/i })).toBeInstanceOf(HTMLButtonElement);
    expect(screen.getByRole("button", { name: /Flag/i })).toBeInstanceOf(HTMLButtonElement);
    expect(screen.getByRole("button", { name: /Skip/i })).toBeInstanceOf(HTMLButtonElement);
  });

  it("Changes Requested dialog exposes dialog semantics", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-changes-requested"));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });
});
