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

export const ingestionApi = {
  upload: (file: File, chapterCode: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("chapter_code", chapterCode);
    return apiClient.postForm<IngestionJob>("/api/v1/ingestion/upload", form);
  },
  jobs: () => apiClient.get<IngestionJob[]>("/api/v1/ingestion/jobs"),
  job: (id: string) => apiClient.get<IngestionJob>(`/api/v1/ingestion/jobs/${id}`),
};
