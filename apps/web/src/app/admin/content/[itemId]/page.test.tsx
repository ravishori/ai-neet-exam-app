import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useParams: () => ({ itemId: "item-1" }),
}));

const get = vi.fn();
const reviewPacket = vi.fn();
vi.mock("@/features/cms/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/cms/api")>("@/features/cms/api");
  return {
    ...actual,
    cmsApi: {
      ...actual.cmsApi,
      get: (...args: unknown[]) => get(...args),
      reviewPacket: (...args: unknown[]) => reviewPacket(...args),
      submit: vi.fn(),
      review: vi.fn(),
      publish: vi.fn(),
      archive: vi.fn(),
    },
  };
});

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
});
