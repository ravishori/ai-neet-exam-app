import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
const push = vi.fn();
const assign = vi.fn();
let search = "status=IN_REVIEW";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push }),
  usePathname: () => "/admin/ai-review",
  useSearchParams: () => new URLSearchParams(search),
}));

beforeEach(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: { assign },
  });
});

const editorialReviewQueue = vi.fn();
const editorialCampaign = vi.fn();
const batchAPilot = vi.fn();
const subjects = vi.fn();

vi.mock("@/features/cms/api", () => ({
  cmsApi: {
    editorialReviewQueue: (...args: unknown[]) => editorialReviewQueue(...args),
    editorialCampaign: (...args: unknown[]) => editorialCampaign(...args),
    batchAPilot: (...args: unknown[]) => batchAPilot(...args),
  },
}));

vi.mock("@/features/academic/api", () => ({
  academicApi: {
    subjects: (...args: unknown[]) => subjects(...args),
  },
}));

import EditorialReviewQueuePage from "@/app/admin/ai-review/page";

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <EditorialReviewQueuePage />
    </QueryClientProvider>,
  );
}

describe("Admin ECAEP queue filters (Phase 3.3-R1)", () => {
  beforeEach(() => {
    replace.mockReset();
    push.mockReset();
    assign.mockReset();
    editorialReviewQueue.mockReset();
    editorialCampaign.mockReset();
    batchAPilot.mockReset();
    subjects.mockReset();
    search = "status=IN_REVIEW";
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: { assign },
    });

    subjects.mockResolvedValue([
      { id: "1", exam_id: "e", code: "PHY", name: "Physics", display_order: 1 },
      { id: "2", exam_id: "e", code: "CHE", name: "Chemistry", display_order: 2 },
      { id: "3", exam_id: "e", code: "BOT", name: "Botany", display_order: 3 },
      { id: "4", exam_id: "e", code: "ZOO", name: "Zoology", display_order: 4 },
    ]);
    editorialCampaign.mockResolvedValue({
      targets: [
        {
          area: "Biology",
          subjects_included: ["Botany", "Zoology"],
          published: 10,
          target: 25,
          remaining: 15,
          progress_ratio: 0.4,
          pipeline: { draft: 0, in_review: 100, approved: 0, changes_requested: 0 },
          pipeline_complete: true,
          met_planning_target: false,
        },
      ],
      status_counts: {
        draft: 1,
        in_review: 100,
        approved: 0,
        published: 10,
        changes_requested: 0,
        archived: 0,
        missing_provenance: 0,
        missing_mapping: 0,
        structurally_invalid: 0,
      },
      count_semantics: {
        status_counts: "COMPLETE",
        by_academic_subject: "COMPLETE",
        "targets.pipeline": "COMPLETE",
      },
      by_academic_subject: [
        {
          subject: "Zoology",
          draft: 0,
          in_review: 100,
          approved: 0,
          published: 5,
          changes_requested: 0,
          archived: 0,
        },
      ],
      chapter_coverage: [],
      quality_metrics: {
        total_questions_scanned: 50,
        sample_limit: 500,
        sample_only: true,
        inventory_total_questions: 200,
        pct_with_provenance: 10,
        pct_with_academic_mapping: 90,
        pct_with_explanation: 80,
        pct_structurally_valid: 70,
        pct_reviewed_or_beyond: 50,
        pct_approved_or_published: 5,
        pct_published: 5,
        disclaimer: "STRUCTURAL SAMPLE ONLY. Scientific validity is never inferred.",
      },
      prioritization: "priority",
      rules: {
        human_review_mandatory: true,
        no_auto_approve: true,
        no_auto_publish: true,
        no_mass_publish_drafts: true,
        planning_target_only: true,
        biology_includes: ["Botany", "Zoology"],
        inventory_counts_complete: true,
      },
    });
    batchAPilot.mockResolvedValue(null);
    editorialReviewQueue.mockResolvedValue({
      data: [
        {
          id: "q1",
          title: "Zoo review item",
          content_type: "QUESTION",
          status: "IN_REVIEW",
          language: "en",
          difficulty: "medium",
          academic: {
            subject: { id: "4", name: "Zoology" },
            chapter: { id: "c", name: "Animal Kingdom" },
            topic: null,
            concept: null,
          },
          structural: { valid: true, issues: [], review_ready: true },
          provenance: { status: "known", has_lineage: true },
          ai_check_flags: [],
          ai_check_status: null,
          chapter_inventory: null,
          explanation_present: true,
          priority_reasons: ["Mapped"],
          campaign_area: "Biology",
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      meta: {
        total: 100,
        limit: 20,
        offset: 0,
        prioritization: "ok",
        ai_disclaimer: "assist",
        recommended_next: null,
      },
    });
  });

  it("renders Subject and Status filters with Zoology and IN_REVIEW", async () => {
    renderPage();
    const subject = await screen.findByTestId("ecaep-subject-filter");
    await waitFor(() => {
      expect(within(subject).getByRole("option", { name: "Zoology" })).toBeInTheDocument();
    });
    const status = screen.getByTestId("ecaep-status-filter");
    expect(within(status).getByRole("option", { name: "IN_REVIEW" })).toBeInTheDocument();
    expect(within(status).getByRole("option", { name: "DRAFT" })).toBeInTheDocument();
  });

  it("calls queue API with Zoology + IN_REVIEW when applied", async () => {
    const user = userEvent.setup();
    renderPage();
    const subject = await screen.findByTestId("ecaep-subject-filter");
    await waitFor(() => {
      expect(within(subject).getByRole("option", { name: "Zoology" })).toBeInTheDocument();
    });

    await user.selectOptions(subject, "Zoology");
    await user.selectOptions(screen.getByTestId("ecaep-status-filter"), "IN_REVIEW");

    const apply = screen.getByTestId("ecaep-apply-filters");
    expect(apply).toHaveAttribute("href", expect.stringContaining("subject_name=Zoology"));
    expect(apply).toHaveAttribute("href", expect.stringContaining("status=IN_REVIEW"));
  });

  it("displays result count from API meta.total", async () => {
    search = "subject_name=Zoology&status=IN_REVIEW";
    renderPage();
    await waitFor(() => {
      expect(editorialReviewQueue).toHaveBeenCalledWith(
        expect.objectContaining({
          subject_name: "Zoology",
          status: "IN_REVIEW",
        }),
      );
    });
    expect(await screen.findByTestId("ecaep-filter-summary")).toHaveTextContent(
      /Zoology · IN_REVIEW · 100 matching/,
    );
  });

  it("reset clears subject and restores default IN_REVIEW URL", async () => {
    search = "subject_name=Chemistry&status=DRAFT&pilot=1&batch_a=1";
    renderPage();
    const reset = await screen.findByTestId("ecaep-reset-filters");
    expect(reset).toHaveAttribute("href", expect.stringContaining("status=IN_REVIEW"));
    expect(reset.getAttribute("href")).not.toContain("subject_name=");
    expect(reset.getAttribute("href")).not.toContain("pilot=");
    expect(reset.getAttribute("href")).not.toContain("batch_a=");
  });

  it("shows empty state when queue returns no rows", async () => {
    editorialReviewQueue.mockResolvedValue({
      data: [],
      meta: { total: 0, limit: 20, offset: 0, prioritization: "", ai_disclaimer: "" },
    });
    search = "subject_name=Chemistry&status=PUBLISHED";
    renderPage();
    expect(await screen.findByText("Nothing in this queue filter")).toBeInTheDocument();
  });

  it("shows queue error state", async () => {
    editorialReviewQueue.mockRejectedValue(new Error("boom"));
    renderPage();
    expect(await screen.findByText(/Queue failed to load/i)).toBeInTheDocument();
  });

  it("campaign panel labels complete pipeline counts", async () => {
    renderPage();
    expect(await screen.findByText(/Inventory snapshot \(complete totals\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Complete pipeline:/i)).toBeInTheDocument();
    expect(screen.getByText(/By academic subject \(complete\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Quality metrics \(structural sample\)/i)).toBeInTheDocument();
  });
});
