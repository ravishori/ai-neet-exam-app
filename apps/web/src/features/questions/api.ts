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

export type QuestionSummary = {
  id: string;
  stem: string | null;
  options: QuestionOption[];
  difficulty: string | null;
  bloom_level: string | null;
  pyq_year: number | null;
  tags: string[];
  language: string;
  concept: NamedRef;
  topic: NamedRef;
  chapter: NamedRef;
  subject: NamedRef;
  images: QuestionImage[];
};

export type ScopeType = "SUBJECT" | "CHAPTER" | "TOPIC" | "CONCEPT";

export type QuestionListParams = {
  scopeType?: ScopeType;
  scopeId?: string;
  limit?: number;
  offset?: number;
};

export type QuestionListResult = {
  data: QuestionSummary[];
  meta: { total: number; limit: number; offset: number };
};

export const questionsApi = {
  list: async (params: QuestionListParams = {}): Promise<QuestionListResult> => {
    const query = new URLSearchParams();
    if (params.scopeType && params.scopeId) {
      query.set("scope_type", params.scopeType);
      query.set("scope_id", params.scopeId);
    }
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<QuestionSummary[]>(`/api/v1/cms/questions?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as QuestionListResult["meta"] };
  },
  get: (id: string) => apiClient.get<QuestionSummary>(`/api/v1/cms/questions/${id}`),
};
