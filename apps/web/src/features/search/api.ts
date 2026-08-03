import { apiClient } from "@/lib/api-client";
import type { NamedRef, QuestionOption, ScopeType } from "@/features/questions/api";

export type SnippetSegment = { text: string; highlighted: boolean };

export type SearchResultItem = {
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
  rank: number;
  snippet: SnippetSegment[];
  matched_fields: string[];
};

export type SearchMode = "fulltext" | "fuzzy" | "empty";

export type SearchParams = {
  q: string;
  scopeType?: ScopeType;
  scopeId?: string;
  difficulty?: string;
  pyqYear?: number;
  limit?: number;
  offset?: number;
};

export type SearchResponse = {
  data: SearchResultItem[];
  meta: { total: number; limit: number; offset: number; search_mode: SearchMode; query: string };
};

const SCOPE_PARAM_BY_TYPE: Record<ScopeType, string> = {
  SUBJECT: "subject_id",
  CHAPTER: "chapter_id",
  TOPIC: "topic_id",
  CONCEPT: "concept_id",
};

export const searchApi = {
  search: async (params: SearchParams): Promise<SearchResponse> => {
    const query = new URLSearchParams();
    query.set("q", params.q);
    if (params.scopeType && params.scopeId) query.set(SCOPE_PARAM_BY_TYPE[params.scopeType], params.scopeId);
    if (params.difficulty) query.set("difficulty", params.difficulty);
    if (params.pyqYear) query.set("pyq_year", String(params.pyqYear));
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<SearchResultItem[]>(`/api/v1/cms/search?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as SearchResponse["meta"] };
  },
};
