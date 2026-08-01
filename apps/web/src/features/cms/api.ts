import { apiClient } from "@/lib/api-client";

export type ContentType = "CONCEPT_NOTE" | "QUESTION" | "FLASHCARD" | "DIAGRAM" | "VIDEO_REF" | "FORMULA_SHEET";
export type WorkflowState = "DRAFT" | "IN_REVIEW" | "CHANGES_REQUESTED" | "APPROVED" | "PUBLISHED" | "ARCHIVED";

export type ContentVersion = {
  id: string;
  version_no: number;
  body: Record<string, unknown>;
  workflow_state: WorkflowState;
  ai_check_report: Record<string, unknown> | null;
  change_summary: string | null;
  authored_by: string | null;
  authored_at: string;
};

export type ContentItem = {
  id: string;
  content_type: ContentType;
  concept_id: string | null;
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
export type QuestionBody = {
  stem: string;
  options: { label: string; text: string }[];
  correct_option: string;
  explanation: string;
  difficulty: string;
  bloom_level?: string;
};

export const cmsApi = {
  list: (params: { content_type?: string; concept_id?: string; status?: string; mine?: boolean } = {}) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return apiClient.get<ContentItem[]>(`/api/v1/cms/content-items${qs ? `?${qs}` : ""}`);
  },
  get: (id: string) => apiClient.get<ContentItem>(`/api/v1/cms/content-items/${id}`),
  versions: (id: string) => apiClient.get<ContentVersion[]>(`/api/v1/cms/content-items/${id}/versions`),
  create: (data: {
    content_type: ContentType;
    concept_id?: string;
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
