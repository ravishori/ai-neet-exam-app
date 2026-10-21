import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useParams: () => ({ questionId: "q1" }),
}));

const detail = vi.fn();
const save = vi.fn();
const skip = vi.fn();
vi.mock("@/features/pyq-answer-review/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/pyq-answer-review/api")>(
    "@/features/pyq-answer-review/api",
  );
  return {
    ...actual,
    pyqAnswerReviewApi: {
      detail: (...args: unknown[]) => detail(...args),
      save: (...args: unknown[]) => save(...args),
      skip: (...args: unknown[]) => skip(...args),
    },
  };
});

import PyqAnswerReviewDetailPage from "@/app/admin/pyq-answer-review/[questionId]/page";

const DETAIL = {
  id: "q1",
  staging_id: "abc123",
  subject: "Physics",
  class_level: "12",
  exam_year: "2024",
  paper_code: "P1",
  paper_id: "paper1",
  state: "ANSWER_PENDING",
  stem: "A charge q moves through a field.",
  options: { A: "opt-a", B: "opt-b", C: "opt-c", D: "opt-d" },
  option_structure: "FOUR_VALID_OPTIONS",
  is_review_eligible: true,
  existing_assertions: [],
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PyqAnswerReviewDetailPage />
    </QueryClientProvider>,
  );
}

describe("PyqAnswerReviewDetailPage", () => {
  it("requires selecting an option and confirming source consultation before Save is enabled", async () => {
    detail.mockResolvedValue(DETAIL);
    renderPage();

    await waitFor(() => expect(screen.getByTestId("option-A")).toBeInTheDocument());
    const saveButton = screen.getByTestId("review-save-button");
    expect(saveButton).toBeDisabled();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("option-B"));
    expect(saveButton).toBeDisabled(); // still disabled: confirmation checkbox not checked

    await user.click(screen.getByTestId("source-consulted-checkbox"));
    expect(saveButton).toBeEnabled();
  });

  it("goes through an explicit confirm step before calling save", async () => {
    detail.mockResolvedValue(DETAIL);
    save.mockResolvedValue({ status: "saved", question_state: "ANSWER_VERIFIED", message: "Saved" });
    renderPage();

    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("option-C")).toBeInTheDocument());
    await user.click(screen.getByTestId("option-C"));
    await user.click(screen.getByTestId("source-consulted-checkbox"));
    await user.click(screen.getByTestId("review-save-button"));

    expect(save).not.toHaveBeenCalled(); // confirm step, not yet submitted
    expect(screen.getByTestId("confirm-save-button")).toBeInTheDocument();

    await user.click(screen.getByTestId("confirm-save-button"));
    await waitFor(() => expect(save).toHaveBeenCalledWith("q1", expect.objectContaining({ asserted_option: "C", source_consulted_confirmed: true })));
  });

  it("shows a banner distinguishing an existing verified answer from a new selection", async () => {
    detail.mockResolvedValue({
      ...DETAIL,
      existing_assertions: [
        {
          asserted_option: "A",
          assertion_source: "human_review:other-reviewer",
          verification_status: "VERIFIED",
          evidence_note: null,
          evidence_source_type: "OFFICIAL_ANSWER_KEY",
          evidence_locator: "Key p.1",
          reviewer_user_id: "other-reviewer",
          reviewed_at: "2026-10-22T00:00:00Z",
          created_at: "2026-10-22T00:00:00Z",
        },
      ],
    });
    renderPage();

    await waitFor(() => expect(screen.getByTestId("existing-verified-banner")).toBeInTheDocument());
    expect(screen.getByTestId("existing-verified-banner")).toHaveTextContent("A");
  });
});
