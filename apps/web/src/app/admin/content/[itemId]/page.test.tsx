import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useParams: () => ({ itemId: "item-1" }),
}));

const get = vi.fn();
const reviewPacket = vi.fn();
const updateDraft = vi.fn();
vi.mock("@/features/cms/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/cms/api")>("@/features/cms/api");
  return {
    ...actual,
    cmsApi: {
      ...actual.cmsApi,
      get: (...args: unknown[]) => get(...args),
      reviewPacket: (...args: unknown[]) => reviewPacket(...args),
      updateDraft: (...args: unknown[]) => updateDraft(...args),
      submit: vi.fn(),
      review: vi.fn(),
      publish: vi.fn(),
      archive: vi.fn(),
    },
  };
});

// ConceptPicker's own queries -- not under test here, just needs to render
// without erroring while the edit form is open.
vi.mock("@/features/academic/api", () => ({
  academicApi: {
    subjects: vi.fn().mockResolvedValue([]),
    chapters: vi.fn().mockResolvedValue([]),
    topics: vi.fn().mockResolvedValue([]),
    concepts: vi.fn().mockResolvedValue([]),
  },
}));

// RichTextEditor wraps Tiptap's contentEditable surface -- its own
// behavior (toolbar commands, Markdown serialization, image upload) is
// out of scope for this page's tests and belongs in a focused test for
// the component itself. Stubbed here as a plain labeled textarea so this
// file can keep testing what IS in scope: that the edit form prefills,
// validates, and saves the right payload.
vi.mock("@/components/rich-text-editor", () => ({
  RichTextEditor: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea aria-label="rich-text-stub" value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));

import ContentDetailPage from "@/app/admin/content/[itemId]/page";
import { ApiError } from "@/lib/api-client";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ContentDetailPage />
    </QueryClientProvider>,
  );
}

const ITEM = {
  id: "item-1",
  content_type: "QUESTION",
  concept_id: null,
  micro_competency_id: null,
  title: "Ohm's law question",
  slug: "ohms-law-question",
  tags: [],
  language: "en",
  status: "IN_REVIEW",
  created_by: null,
  current_version: null,
  latest_version: {
    id: "v1",
    version_no: 1,
    body: {},
    workflow_state: "IN_REVIEW",
    ai_check_report: null,
    change_summary: null,
    authored_by: null,
    authored_at: new Date().toISOString(),
  },
};

const BASE_PACKET = {
  item_id: "item-1",
  title: ITEM.title,
  content_type: "QUESTION",
  status: "IN_REVIEW",
  language: "en",
  tags: [],
  concept_id: null,
  academic: null,
  body: {},
  provenance: {
    model_used: null,
    knowledge_unit_id: null,
    knowledge_unit_version: null,
    prompt_version: null,
    confidence_score: null,
    generation_cost_usd: null,
    has_lineage: false,
    status: "missing",
  },
  structural: { valid: true, issues: [], review_ready: true },
  suspected_duplicates: [],
  reviews: [],
  ai_assistance: { report: null, disclaimer: "AI assistance only." },
  checklist: [],
  chapter_inventory: null,
  campaign_notes: { target: "", do_not_mass_publish: true, human_review_mandatory: true },
  allowed_decisions: ["approve", "request_changes"],
};

describe("admin content detail page", () => {
  beforeEach(() => {
    get.mockReset();
    reviewPacket.mockReset();
    updateDraft.mockReset();
  });

  it("shows a loading state before data resolves", async () => {
    get.mockReturnValue(new Promise(() => {}));
    reviewPacket.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders a clean not-found state on 404 without crashing", async () => {
    get.mockRejectedValue(new ApiError("Not found", "NOT_FOUND", 404));
    reviewPacket.mockRejectedValue(new ApiError("Not found", "NOT_FOUND", 404));
    renderPage();
    await waitFor(() => expect(screen.getByText(/not found/i)).toBeInTheDocument());
  });

  it("renders an unauthorized state on 403 without crashing", async () => {
    get.mockRejectedValue(new ApiError("Forbidden", "FORBIDDEN", 403));
    reviewPacket.mockRejectedValue(new ApiError("Forbidden", "FORBIDDEN", 403));
    renderPage();
    await waitFor(() => expect(screen.getByText(/don't have permission/i)).toBeInTheDocument());
  });

  it("renders a retryable error state on an unexpected failure instead of crashing", async () => {
    get.mockRejectedValue(new ApiError("Server error", "INTERNAL", 500));
    reviewPacket.mockRejectedValue(new ApiError("Server error", "INTERNAL", 500));
    renderPage();
    await waitFor(() => expect(screen.getByText(/couldn't load this content item/i)).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders question options normally when present", async () => {
    get.mockResolvedValue(ITEM);
    reviewPacket.mockResolvedValue({
      ...BASE_PACKET,
      question: {
        stem: "What does Ohm's law relate?",
        options: [
          { label: "A", text: "V, I, R" },
          { label: "B", text: "Force and mass" },
        ],
        correct_option: "A",
        explanation: "V = IR",
        difficulty: "easy",
      },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/what does ohm's law relate/i)).toBeInTheDocument());
    expect(screen.getByText("V, I, R")).toBeInTheDocument();
  });

  // Regression: malformed/legacy content rows can have body.options stored as JSON
  // null rather than merely absent. The backend now normalizes this to [] (see
  // apps/backend/app/modules/cms/services/editorial_review_service.py), but the
  // component must also not crash if a null ever slips through, since a `.map()`
  // on null/undefined previously took down the whole page via the generic
  // Next.js error boundary ("Something went wrong").
  it("does not crash when question.options is null", async () => {
    get.mockResolvedValue(ITEM);
    reviewPacket.mockResolvedValue({
      ...BASE_PACKET,
      question: {
        stem: "Malformed legacy question",
        options: null,
        correct_option: "A",
        explanation: "",
        difficulty: "easy",
      },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/malformed legacy question/i)).toBeInTheDocument());
    expect(screen.getByText(/no options recorded/i)).toBeInTheDocument();
  });

  it("does not crash when question.options is undefined", async () => {
    get.mockResolvedValue(ITEM);
    reviewPacket.mockResolvedValue({
      ...BASE_PACKET,
      question: {
        stem: "Question missing options key",
        correct_option: "A",
        explanation: "",
        difficulty: "easy",
      },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/question missing options key/i)).toBeInTheDocument());
    expect(screen.getByText(/no options recorded/i)).toBeInTheDocument();
  });

  it("renders an empty-options state distinctly (no options, no crash, no false 'correct' badge)", async () => {
    get.mockResolvedValue(ITEM);
    reviewPacket.mockResolvedValue({
      ...BASE_PACKET,
      question: {
        stem: "Stem with zero options",
        options: [],
        correct_option: "A",
        explanation: "",
        difficulty: "easy",
      },
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/stem with zero options/i)).toBeInTheDocument());
    expect(screen.getByText(/no options recorded/i)).toBeInTheDocument();
    expect(screen.queryByText("Correct")).not.toBeInTheDocument();
  });

  const EDITABLE_QUESTION = {
    stem: "What does Ohm's law relate?",
    options: [
      { label: "A", text: "V, I, R" },
      { label: "B", text: "Force and mass" },
      { label: "C", text: "Charge and time" },
      { label: "D", text: "Energy and power only" },
    ],
    correct_option: "A",
    explanation: "V = IR",
    difficulty: "easy",
  };

  async function openEditor() {
    get.mockResolvedValue(ITEM);
    reviewPacket.mockResolvedValue({ ...BASE_PACKET, question: EDITABLE_QUESTION });
    renderPage();
    await waitFor(() => expect(screen.getByText(/what does ohm's law relate/i)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
    await waitFor(() => expect(screen.getByLabelText(/change summary/i)).toBeInTheDocument());
  }

  it("opens the edit form prefilled with the current stem, options, and explanation", async () => {
    await openEditor();
    expect(screen.getByDisplayValue(EDITABLE_QUESTION.stem)).toBeInTheDocument();
    expect(screen.getByDisplayValue("V, I, R")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Force and mass")).toBeInTheDocument();
    expect(screen.getByDisplayValue("V = IR")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled();
  });

  it("Cancel closes the edit form without calling updateDraft", async () => {
    await openEditor();
    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));
    await waitFor(() => expect(screen.queryByLabelText(/change summary/i)).not.toBeInTheDocument());
    expect(screen.getByText(/what does ohm's law relate/i)).toBeInTheDocument();
    expect(updateDraft).not.toHaveBeenCalled();
  });

  it("Save stays disabled until stem, all options, and a non-empty change summary are present", async () => {
    await openEditor();
    const saveButton = screen.getByRole("button", { name: /^save$/i });
    // Prefilled stem/options/correct_option are already valid; only the
    // (required, not prefilled) change summary is missing.
    expect(saveButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/change summary/i), { target: { value: "Fixed a typo" } });
    expect(saveButton).toBeEnabled();

    // Clearing a previously-filled option must re-disable Save.
    fireEvent.change(screen.getByDisplayValue("Force and mass"), { target: { value: "" } });
    expect(saveButton).toBeDisabled();
  });

  it("Save calls updateDraft with the edited fields, change summary, and selected correct option", async () => {
    updateDraft.mockResolvedValue({
      ...ITEM,
      status: "DRAFT",
      latest_version: { ...ITEM.latest_version, id: "v2", version_no: 2, body: EDITABLE_QUESTION },
    });
    await openEditor();

    fireEvent.change(screen.getByDisplayValue(EDITABLE_QUESTION.stem), { target: { value: "Corrected stem" } });
    fireEvent.click(screen.getByDisplayValue("Force and mass").closest("div")!.querySelector('input[type="radio"]')!);
    fireEvent.change(screen.getByLabelText(/change summary/i), { target: { value: "Corrected stem and answer" } });

    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(updateDraft).toHaveBeenCalledTimes(1));
    const [calledItemId, payload] = updateDraft.mock.calls[0];
    expect(calledItemId).toBe("item-1");
    expect(payload.change_summary).toBe("Corrected stem and answer");
    expect(payload.body.stem).toBe("Corrected stem");
    expect(payload.body.correct_option).toBe("B");
    expect(payload.body.answer_status).toBe("ANSWER_PENDING"); // "Mark answer verified" left unchecked
  });

  it("save/reload: a successful save closes the editor and the page reflects the refetched content", async () => {
    updateDraft.mockResolvedValue({
      ...ITEM,
      status: "DRAFT",
      latest_version: { ...ITEM.latest_version, id: "v2", version_no: 2, body: EDITABLE_QUESTION },
    });
    await openEditor();

    // After save, a refetch is triggered (query invalidation) -- simulate
    // the server now returning the saved stem, proving the page re-reads
    // from the backend rather than trusting only its own local form state.
    reviewPacket.mockResolvedValue({
      ...BASE_PACKET,
      question: { ...EDITABLE_QUESTION, stem: "Reloaded from server" },
    });

    fireEvent.change(screen.getByLabelText(/change summary/i), { target: { value: "Save/reload check" } });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(screen.queryByLabelText(/change summary/i)).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Reloaded from server")).toBeInTheDocument());
  });

  it("shows a server validation error (e.g. missing answer evidence) without crashing or losing form state", async () => {
    updateDraft.mockRejectedValue(
      new ApiError("Content body failed publishing quality gates. Fix the draft and re-approve before publishing.", "INVALID_CONTENT_BODY", 422),
    );
    await openEditor();

    fireEvent.change(screen.getByLabelText(/change summary/i), { target: { value: "Attempted save" } });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(screen.getByText(/failed publishing quality gates/i)).toBeInTheDocument());
    // Form stays open with the entered data intact -- nothing was silently discarded.
    expect(screen.getByLabelText(/change summary/i)).toHaveValue("Attempted save");
  });

  it(
    "reproduces the reported production case (7fb11a6b-...): a legacy question with " +
      "null explanation opens with Save disabled, explains exactly why, and enables " +
      "once explanation and change summary are filled in",
    async () => {
      const legacyQuestion = {
        ...EDITABLE_QUESTION,
        stem: "Match the following columns and select the correct option.",
        explanation: null, // the actual stored shape for this item
      };
      get.mockResolvedValue(ITEM);
      reviewPacket.mockResolvedValue({ ...BASE_PACKET, question: legacyQuestion });
      renderPage();
      await waitFor(() => expect(screen.getByText(/match the following columns/i)).toBeInTheDocument());
      fireEvent.click(screen.getByRole("button", { name: /^edit$/i }));
      await waitFor(() => expect(screen.getByLabelText(/change summary/i)).toBeInTheDocument());

      // Stem and options and correct_option are already filled from the
      // packet; only explanation (null -> "") and change summary are not.
      const saveButton = screen.getByRole("button", { name: /^save$/i });
      expect(saveButton).toBeDisabled();
      const reasons = screen.getByTestId("save-blocked-reasons").textContent ?? "";
      expect(reasons).toMatch(/explanation/i);
      expect(reasons).toMatch(/change summary/i);
      expect(reasons).not.toMatch(/stem/i);
      expect(reasons).not.toMatch(/option/i);

      const [stemField, explanationField] = screen.getAllByLabelText("rich-text-stub");
      expect(stemField).toHaveValue(legacyQuestion.stem);
      expect(explanationField).toHaveValue(""); // confirms the blank box is genuinely empty, not a sync bug

      fireEvent.change(explanationField, { target: { value: "Filled in by SME during correction." } });
      expect(saveButton).toBeDisabled(); // change summary still missing
      expect(screen.getByTestId("save-blocked-reasons").textContent).toMatch(/change summary/i);
      expect(screen.queryByTestId("save-blocked-reasons")?.textContent).not.toMatch(/explanation/i);

      fireEvent.change(screen.getByLabelText(/change summary/i), {
        target: { value: "Filled missing explanation" },
      });
      expect(saveButton).toBeEnabled();
      expect(screen.queryByTestId("save-blocked-reasons")).not.toBeInTheDocument();

      updateDraft.mockResolvedValue({
        ...ITEM,
        status: "DRAFT",
        latest_version: { ...ITEM.latest_version, id: "v2", version_no: 2, body: legacyQuestion },
      });
      fireEvent.click(saveButton);

      await waitFor(() => expect(updateDraft).toHaveBeenCalledTimes(1));
      const [, payload] = updateDraft.mock.calls[0];
      expect(payload.body.explanation).toBe("Filled in by SME during correction.");
      expect(payload.change_summary).toBe("Filled missing explanation");
    },
  );
});
