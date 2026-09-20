import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

let search = new URLSearchParams("pilot=pilot-test");
vi.mock("next/navigation", () => ({
  useParams: () => ({ sessionId: "sess-1" }),
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => search,
}));

const getReviewSession = vi.fn();
const advanceReviewSession = vi.fn();
const claimReviewItem = vi.fn();
const reviewPacket = vi.fn();
const review = vi.fn();
const recordPilotEvent = vi.fn();

vi.mock("@/features/cms/api", () => ({
  cmsApi: {
    getReviewSession: (...args: unknown[]) => getReviewSession(...args),
    advanceReviewSession: (...args: unknown[]) => advanceReviewSession(...args),
    claimReviewItem: (...args: unknown[]) => claimReviewItem(...args),
    reviewPacket: (...args: unknown[]) => reviewPacket(...args),
    review: (...args: unknown[]) => review(...args),
    recordPilotEvent: (...args: unknown[]) => recordPilotEvent(...args),
  },
}));

import ReviewSessionPage from "@/app/admin/content/review-queue/session/[sessionId]/page";

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
    body: { ncert_evidence: null },
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

describe("HR-2.5 pilot instrumentation (?pilot= query param)", () => {
  beforeEach(() => {
    search = new URLSearchParams("pilot=pilot-test");
    getReviewSession.mockReset();
    advanceReviewSession.mockReset();
    claimReviewItem.mockReset();
    reviewPacket.mockReset();
    review.mockReset();
    recordPilotEvent.mockReset();

    getReviewSession.mockResolvedValue(baseSession());
    claimReviewItem.mockResolvedValue({ id: "claim-1", status: "ACTIVE" });
    reviewPacket.mockImplementation((id: string) => Promise.resolve(basePacket(id)));
    recordPilotEvent.mockResolvedValue({ id: "evt-1" });
  });

  it("records an APPROVED pilot event with timing and subject/chapter on approve", async () => {
    review.mockResolvedValue({ id: "q1", status: "APPROVED" });
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-approve"));
    await waitFor(() =>
      expect(recordPilotEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          pilot_id: "pilot-test",
          content_item_id: "q1",
          decision: "APPROVED",
          subject: "Physics",
          chapter: "Current Electricity",
        }),
      ),
    );
    const call = recordPilotEvent.mock.calls[0][0];
    expect(typeof call.review_started_at).toBe("string");
    expect(typeof call.decision_submitted_at).toBe("string");
    expect(call.review_duration_seconds).toBeGreaterThanOrEqual(0);
  });

  it("records a SKIPPED pilot event on skip", async () => {
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-skip"));
    await waitFor(() =>
      expect(recordPilotEvent).toHaveBeenCalledWith(expect.objectContaining({ decision: "SKIPPED" })),
    );
  });

  it("records a FLAGGED pilot event with reason OTHER on flag", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-flag"));
    await waitFor(() =>
      expect(recordPilotEvent).toHaveBeenCalledWith(expect.objectContaining({ decision: "FLAGGED", reason: "OTHER" })),
    );
  });

  it("records a CHANGES_REQUESTED pilot event with the mapped machine reason code", async () => {
    review.mockResolvedValue({ id: "q1", status: "CHANGES_REQUESTED" });
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-changes-requested"));
    await user.selectOptions(screen.getByTestId("changes-reason-select"), "Duplicate");
    await user.click(screen.getByTestId("submit-changes-requested"));
    await waitFor(() =>
      expect(recordPilotEvent).toHaveBeenCalledWith(expect.objectContaining({ decision: "CHANGES_REQUESTED", reason: "DUPLICATE" })),
    );
  });

  it("does not record any pilot event when ?pilot= is absent (ordinary HR-2 usage unaffected)", async () => {
    search = new URLSearchParams();
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-skip"));
    await waitFor(() => expect(advanceReviewSession).toHaveBeenCalled());
    expect(recordPilotEvent).not.toHaveBeenCalled();
  });

  it("a failed pilot-event write never blocks the real approve action", async () => {
    review.mockResolvedValue({ id: "q1", status: "APPROVED" });
    advanceReviewSession.mockResolvedValue(baseSession({ position: 1, current_item_id: "q2", remaining: 1 }));
    recordPilotEvent.mockRejectedValue(new Error("network blip"));
    const user = userEvent.setup();
    renderPage();
    await screen.findByTestId("question-stem");
    await user.click(screen.getByTestId("action-approve"));
    await waitFor(() => expect(advanceReviewSession).toHaveBeenCalled());
    expect(await screen.findByTestId("question-stem")).toHaveTextContent("Stem for q2");
  });
});
