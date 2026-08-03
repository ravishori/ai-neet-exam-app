import { apiClient } from "@/lib/api-client";

export type ContentType = "CONCEPT_NOTE" | "QUESTION" | "FLASHCARD" | "DIAGRAM" | "VIDEO_REF" | "FORMULA_SHEET";
export type WorkflowState = "DRAFT" | "IN_REVIEW" | "CHANGES_REQUESTED" | "APPROVED" | "PUBLISHED" | "ARCHIVED";

export type AiCheckReport = {
  status: "completed" | "skipped" | "error";
  reason: string;
  flags: string[];
  confidence: number | null;
  checked_at: string;
};

export type ContentVersion = {
  id: string;
  version_no: number;
  body: Record<string, unknown>;
  workflow_state: WorkflowState;
  ai_check_report: AiCheckReport | null;
  change_summary: string | null;
  authored_by: string | null;
  authored_at: string;
};

export type ContentItem = {
  id: string;
  content_type: ContentType;
  concept_id: string | null;
  micro_competency_id: string | null;
  title: string;
  slug: string;
  tags: string[];
  language: string;
  status: WorkflowState;
  created_by: string | null;
  current_version: ContentVersion | null;
  latest_version: ContentVersion | null;
};

export type CoverageRow = {
  concept_id: string;
  concept_name: string;
  subject_name: string;
  chapter_name: string;
  published_content_types: string[];
};

export type ConceptNoteBody = { ncert_ref?: string; summary: string; sections: string[] };
export type FlashcardBody = { front: string; back: string; image_url?: string | null };
export type QuestionBody = {
  stem: string;
  options: { label: string; text: string }[];
  correct_option: string;
  explanation: string;
  difficulty: string;
  bloom_level?: string;
};

export type ContentReport = {
  id: string;
  content_item_id: string;
  reported_by: string;
  reason: string;
  comment: string | null;
  status: "OPEN" | "RESOLVED" | "DISMISSED";
  created_at: string;
};

export type ListParams = {
  content_type?: string;
  concept_id?: string;
  status?: string;
  search?: string;
  mine?: boolean;
  limit?: number;
  offset?: number;
};

export type ListResult = { data: ContentItem[]; meta: { total: number; limit: number; offset: number } };

export type BulkActionResult = { id: string; success: boolean; error?: string };

export const cmsApi = {
  list: async (params: ListParams = {}): Promise<ListResult> => {
    const query = new URLSearchParams();
    if (params.content_type) query.set("content_type", params.content_type);
    if (params.concept_id) query.set("concept_id", params.concept_id);
    if (params.status) query.set("status", params.status);
    if (params.search) query.set("search", params.search);
    if (params.mine) query.set("mine", "true");
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<ContentItem[]>(`/api/v1/cms/content-items?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as ListResult["meta"] };
  },
  bulkAction: (itemIds: string[], action: "publish" | "archive") =>
    apiClient.post<BulkActionResult[]>("/api/v1/cms/content-items/bulk", { item_ids: itemIds, action }),
  listReports: async (params: { status?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<ContentReport[]>(`/api/v1/cms/content-reports?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as ListResult["meta"] };
  },
  resolveReport: (id: string, status: "RESOLVED" | "DISMISSED") =>
    apiClient.patch<ContentReport>(`/api/v1/cms/content-reports/${id}`, { status }),
  aiReviewQueue: async (params: { status?: string; limit?: number; offset?: number } = {}): Promise<ListResult> => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<ContentItem[]>(`/api/v1/cms/ai-review-queue?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as ListResult["meta"] };
  },
  get: (id: string) => apiClient.get<ContentItem>(`/api/v1/cms/content-items/${id}`),
  versions: (id: string) => apiClient.get<ContentVersion[]>(`/api/v1/cms/content-items/${id}/versions`),
  create: (data: {
    content_type: ContentType;
    concept_id?: string;
    micro_competency_id?: string;
    title: string;
    slug: string;
    tags?: string[];
    language?: string;
    body: Record<string, unknown>;
  }) => apiClient.post<ContentItem>("/api/v1/cms/content-items", data),
  updateDraft: (id: string, data: { body: Record<string, unknown>; change_summary?: string }) =>
    apiClient.patch<ContentItem>(`/api/v1/cms/content-items/${id}`, data),
  submit: (id: string) => apiClient.post<ContentItem>(`/api/v1/cms/content-items/${id}/submit`),
  review: (id: string, data: { decision: "approve" | "request_changes"; comment?: string }) =>
    apiClient.post<ContentItem>(`/api/v1/cms/content-items/${id}/review`, data),
  publish: (id: string) => apiClient.post<ContentItem>(`/api/v1/cms/content-items/${id}/publish`),
  archive: (id: string) => apiClient.post<ContentItem>(`/api/v1/cms/content-items/${id}/archive`),
  coverage: () => apiClient.get<CoverageRow[]>("/api/v1/cms/coverage"),
  publishedForConcept: async (conceptId: string, language?: string) => {
    const qs = language ? `?language=${encodeURIComponent(language)}` : "";
    const envelope = await apiClient.getFull<ContentItem[]>(`/api/v1/cms/concepts/${conceptId}/published${qs}`);
    return {
      items: envelope.data ?? [],
      language: (envelope.meta.language as string) ?? "en",
      languageFallback: Boolean(envelope.meta.language_fallback),
    };
  },
};
