import { apiClient } from "@/lib/api-client";

export type ValidationStatus = "PENDING" | "PASSED" | "FAILED";

export type KnowledgeUnitSummary = {
  id: string;
  version: number;
  summary: string;
  concept_id: string;
  concept_name: string | null;
  extraction_confidence: number;
  validation_status: ValidationStatus;
  validation_detail: string | null;
  superseded_by: string | null;
  created_at: string;
};

export type KnowledgeUnitDetail = KnowledgeUnitSummary & {
  structured_facts: unknown[];
  source_section: { id: string; heading: string | null; source_page: number | null } | null;
  visual_assets: { id: string; asset_type: string; review_status: string }[];
  supersede_chain: string[];
};

export type KnowledgeUnitListParams = {
  validationStatus?: ValidationStatus;
  conceptId?: string;
  limit?: number;
  offset?: number;
};

export type KnowledgeUnitListResult = { data: KnowledgeUnitSummary[]; meta: { total: number; limit: number; offset: number } };

export const knowledgeApi = {
  list: async (params: KnowledgeUnitListParams = {}): Promise<KnowledgeUnitListResult> => {
    const query = new URLSearchParams();
    if (params.validationStatus) query.set("validation_status", params.validationStatus);
    if (params.conceptId) query.set("concept_id", params.conceptId);
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<KnowledgeUnitSummary[]>(`/api/v1/knowledge/units?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as KnowledgeUnitListResult["meta"] };
  },
  get: (id: string) => apiClient.get<KnowledgeUnitDetail>(`/api/v1/knowledge/units/${id}`),
};
