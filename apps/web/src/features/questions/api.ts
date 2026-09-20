import { apiClient } from "@/lib/api-client";

export type QuestionOption = { label: string; text: string };

export type NamedRef = { id: string; name: string } | null;

export type QuestionImage = {
  id: string;
  asset_type: string;
  alt_text: string | null;
  width_px: number | null;
  height_px: number | null;
};

export type QuestionProvenance = {
  source: "PROJECT_AUTHORED" | "NCERT_INGESTED" | "AI_GENERATED";
  ncert_verification_level: string | null;
  ncert_reference_tag: string | null;
  source_pdf: string | null;
  model_used: string | null;
  prompt_version: string | null;
  confidence_score: number | null;
  knowledge_unit_id: string | null;
  authored_at: string | null;
};

export type QuestionSummary = {
  id: string;
  stem: string | null;
  options: QuestionOption[];
  difficulty: string | null;
  bloom_level: string | null;
  pyq_year: number | null;
  question_type: "MCQ";
  tags: string[];
  language: string;
  concept: NamedRef;
  topic: NamedRef;
  chapter: NamedRef;
  subject: NamedRef;
  ncert_reference: string | null;
  class_level: "11" | "12" | null;
  provenance: QuestionProvenance;
  images: QuestionImage[];
};

export type ReportReason = "WRONG_ANSWER" | "UNCLEAR" | "TYPO" | "OFFENSIVE" | "OTHER";

export type ScopeType = "SUBJECT" | "CHAPTER" | "TOPIC" | "CONCEPT";
export type ClassLevel = "11" | "12";

export type QuestionListParams = {
  scopeType?: ScopeType;
  scopeId?: string;
  classLevel?: ClassLevel;
  limit?: number;
  offset?: number;
};

export type QuestionListResult = {
  data: QuestionSummary[];
  meta: { total: number; limit: number; offset: number; class_level: ClassLevel | null };
};

export const questionsApi = {
  list: async (params: QuestionListParams = {}): Promise<QuestionListResult> => {
    const query = new URLSearchParams();
    if (params.scopeType && params.scopeId) {
      query.set("scope_type", params.scopeType);
      query.set("scope_id", params.scopeId);
    }
    if (params.classLevel) query.set("class_level", params.classLevel);
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<QuestionSummary[]>(`/api/v1/cms/questions?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as QuestionListResult["meta"] };
  },
  get: (id: string) => apiClient.get<QuestionSummary>(`/api/v1/cms/questions/${id}`),
  related: (id: string) => apiClient.get<QuestionSummary[]>(`/api/v1/cms/questions/${id}/related`),
  report: (id: string, data: { reason: ReportReason; comment?: string }) =>
    apiClient.post<{ reported: boolean }>(`/api/v1/cms/questions/${id}/report`, data),
};
