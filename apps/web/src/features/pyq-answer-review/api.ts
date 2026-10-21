import { apiClient } from "@/lib/api-client";

export type OptionStructure = "FOUR_VALID_OPTIONS" | "MISSING_OPTION" | "DUPLICATE_OPTIONS" | "MALFORMED_OPTIONS" | "REQUIRES_MANUAL_REVIEW";
export type EvidenceSourceType = "OFFICIAL_ANSWER_KEY" | "TEXTBOOK_REFERENCE" | "EXPERT_REVIEW" | "OTHER";

export type QueueCounts = {
  eligible: number;
  requires_manual_review: number;
  structurally_invalid: number;
  total_pending: number;
  reviewed_by_human: number;
  skipped: number;
};

export type QueueItem = {
  id: string;
  staging_id: string;
  subject: string | null;
  class_level: string | null;
  exam_year: string | null;
  paper_code: string | null;
  stem_preview: string;
};

export type QueueListResult = {
  items: QueueItem[];
  page: number;
  page_size: number;
  returned: number;
};

export type QueueFilters = {
  exam_year?: string;
  subject?: string;
  search?: string;
  page?: number;
  page_size?: number;
};

export type ExistingAssertion = {
  asserted_option: string;
  assertion_source: string;
  verification_status: string;
  evidence_note: string | null;
  evidence_source_type: string | null;
  evidence_locator: string | null;
  reviewer_user_id: string | null;
  reviewed_at: string | null;
  created_at: string | null;
};

export type QuestionReviewDetail = {
  id: string;
  staging_id: string;
  subject: string | null;
  class_level: string | null;
  exam_year: string | null;
  paper_code: string | null;
  paper_id: string | null;
  state: string;
  stem: string;
  options: Record<string, string | null>;
  option_structure: OptionStructure;
  is_review_eligible: boolean;
  existing_assertions: ExistingAssertion[];
};

export type SaveReviewPayload = {
  asserted_option: string;
  evidence_source_type: EvidenceSourceType;
  evidence_locator?: string | null;
  review_note?: string | null;
  expected_state: string;
  source_consulted_confirmed: boolean;
};

export type SaveReviewResult = {
  status: "saved" | "idempotent_noop" | "conflict_recorded";
  question_state: string;
  message: string;
};

export const pyqAnswerReviewApi = {
  counts: () => apiClient.get<QueueCounts>("/api/v1/admin/pyq-answer-review/counts"),

  list: (filters: QueueFilters) => {
    const query = new URLSearchParams();
    if (filters.exam_year) query.set("exam_year", filters.exam_year);
    if (filters.subject) query.set("subject", filters.subject);
    if (filters.search) query.set("search", filters.search);
    query.set("page", String(filters.page ?? 1));
    query.set("page_size", String(filters.page_size ?? 25));
    return apiClient.get<QueueListResult>(`/api/v1/admin/pyq-answer-review?${query.toString()}`);
  },

  detail: (questionId: string) =>
    apiClient.get<QuestionReviewDetail>(`/api/v1/admin/pyq-answer-review/${questionId}`),

  save: (questionId: string, payload: SaveReviewPayload) =>
    apiClient.post<SaveReviewResult>(`/api/v1/admin/pyq-answer-review/${questionId}/review`, payload),

  skip: (questionId: string) =>
    apiClient.post<{ status: string }>(`/api/v1/admin/pyq-answer-review/${questionId}/skip`, {}),
};
