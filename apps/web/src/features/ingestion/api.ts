import { apiClient } from "@/lib/api-client";

export type IngestionJobStatus =
  | "PENDING"
  | "EXTRACTING"
  | "MATCHING"
  | "STRUCTURING"
  | "GENERATING"
  | "COMPLETED"
  | "FAILED";

export type IngestionJob = {
  id: string;
  source_file_path: string;
  original_filename: string | null;
  status: IngestionJobStatus;
  stage_detail: string | null;
  error_message: string | null;
  sections_detected: number;
  questions_generated: number;
  questions_deduped: number;
  flashcards_generated: number;
  notes_generated: number;
  revision_sheets_generated: number;
  knowledge_units_created: number;
  knowledge_units_rejected: number;
  visual_assets_detected: number;
  visual_assets_needing_review: number;
  created_at: string;
  updated_at: string;
};

export type IngestionJobSection = { id: string; heading: string | null; source_page: number | null; matched_concept_id: string | null };
export type IngestionJobKnowledgeUnit = { id: string; summary: string; validation_status: string };
export type IngestionJobVisualAsset = { id: string; asset_type: string; review_status: string; source_page: number | null };

export type IngestionJobDetail = IngestionJob & {
  sections: IngestionJobSection[];
  knowledge_units: IngestionJobKnowledgeUnit[];
  visual_assets: IngestionJobVisualAsset[];
};

export type JobListParams = { status?: IngestionJobStatus; limit?: number; offset?: number };
export type JobListResult = { data: IngestionJob[]; meta: { total: number; limit: number; offset: number } };

export const ingestionApi = {
  upload: (file: File, chapterCode: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("chapter_code", chapterCode);
    return apiClient.postForm<IngestionJob>("/api/v1/ingestion/upload", form);
  },
  jobs: () => apiClient.get<IngestionJob[]>("/api/v1/ingestion/jobs"),
  jobsPaginated: async (params: JobListParams = {}): Promise<JobListResult> => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<IngestionJob[]>(`/api/v1/ingestion/jobs?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as JobListResult["meta"] };
  },
  job: (id: string) => apiClient.get<IngestionJob>(`/api/v1/ingestion/jobs/${id}`),
  jobDetail: (id: string) => apiClient.get<IngestionJobDetail>(`/api/v1/ingestion/jobs/${id}/detail`),
};
