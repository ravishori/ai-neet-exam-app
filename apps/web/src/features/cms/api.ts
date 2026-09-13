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
  knowledge_unit_id?: string | null;
  knowledge_unit_version?: number | null;
  model_used?: string | null;
  prompt_version?: string | null;
  confidence_score?: number | null;
  generation_cost_usd?: number | null;
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

export type EditorialNamedNode = { id: string; name: string } | null;

export type EditorialQueueRow = {
  id: string;
  title: string;
  content_type: string;
  status: WorkflowState;
  language: string;
  difficulty: string | null;
  academic: {
    subject: EditorialNamedNode;
    chapter: EditorialNamedNode;
    topic: EditorialNamedNode;
    concept: EditorialNamedNode;
  };
  structural: { valid: boolean; issues: string[]; review_ready: boolean };
  provenance: {
    status: string;
    has_lineage: boolean;
    model_used?: string | null;
    label?: string | null;
  };
  ai_check_flags: string[];
  ai_check_status: string | null;
  chapter_inventory: {
    chapter_name: string;
    subject_name: string;
    draft: number;
    in_review: number;
    published: number;
  } | null;
  explanation_present: boolean;
  priority_reasons?: string[];
  campaign_area?: string | null;
  batch_a?: boolean;
  created_at: string;
};

export type EditorialQueueMeta = {
  total: number;
  limit: number;
  offset: number;
  prioritization: string;
  ai_disclaimer: string;
  recommended_next?: { id: string; title: string; priority_reasons: string[] } | null;
  quality_vs_science?: string;
  pilot_only?: boolean;
  batch_tag?: string | null;
};

export type ReviewChecklistItem = { id: string; category: string; prompt: string };

export type BatchAPilotReport = {
  pilot_id: string;
  batch_id: string;
  targets: Record<string, number>;
  selected_count: number;
  batch_a_total: number;
  remaining_batch_a_untouched: number;
  selection_notes: Record<string, string>;
  selected: {
    id: string;
    slug: string;
    title: string;
    status: WorkflowState;
    subject: string;
    chapter: string;
    topic: string;
    concept: string;
    difficulty: string | null;
    pilot_label?: string;
    pilot_rank?: number;
    priority_reasons?: string[];
    structural: { valid: boolean; review_ready: boolean };
    provenance: { status: string; has_lineage: boolean; label: string; sme_review_required: boolean };
    model_used?: string | null;
  }[];
  remaining_ids: string[];
  distributions: {
    subject: Record<string, number>;
    chapter: Record<string, number>;
    topic: Record<string, number>;
    difficulty: Record<string, number>;
    status: Record<string, number>;
  };
  checklist: ReviewChecklistItem[];
  rules: Record<string, boolean>;
};

export type ReviewPacket = {
  item_id: string;
  title: string;
  content_type: ContentType;
  status: WorkflowState;
  language: string;
  tags: string[];
  concept_id: string | null;
  academic: {
    concept?: EditorialNamedNode;
    topic?: EditorialNamedNode;
    chapter?: EditorialNamedNode;
    subject?: EditorialNamedNode;
    ncert_reference?: string | null;
  } | null;
  question: QuestionBody & { bloom_level?: string; pyq_year?: number | null } | null;
  body: Record<string, unknown>;
  provenance: {
    model_used: string | null;
    knowledge_unit_id: string | null;
    knowledge_unit_version: number | null;
    prompt_version: string | null;
    confidence_score: number | null;
    generation_cost_usd: number | null;
    has_lineage: boolean;
    status: string;
    source_verification_required?: boolean;
    display_note?: string;
    display_label?: string | null;
  };
  batch_a?: {
    is_batch_a: boolean;
    display_label: string | null;
    sme_review_required: boolean | null;
    not_official_nta_ncert: boolean | null;
  };
  structural: { valid: boolean; issues: string[]; review_ready: boolean; note?: string };
  suspected_duplicates: { id: string; title: string; status: string; stem_preview: string }[];
  reviews: { id: string; reviewer_id: string | null; decision: string; comment: string | null; reviewed_at: string }[];
  ai_assistance: { report: AiCheckReport | null; disclaimer: string };
  factory_qa?: {
    present: boolean;
    classification?: string;
    qa_version?: string;
    failed_checks?: string[];
    warnings?: string[];
    duplicate_class?: string;
    quarantine?: boolean;
    scientific_certification?: boolean;
    disclaimer: string;
    factory_review?: {
      factory_review_item_id: string;
      selection_class: string;
      review_status: string;
      decision: string | null;
      ecaep_submit_eligible: boolean;
      failure_reasons: string[];
      disclaimer: string;
    } | null;
  };
  checklist: ReviewChecklistItem[];
  review_notes_guidance?: {
    encourage_notes: boolean;
    examples: string[];
    student_visibility: string;
  };
  chapter_inventory: {
    chapter_name: string;
    subject_name: string;
    draft: number;
    in_review: number;
    published: number;
  } | null;
  campaign_notes: {
    target: string;
    do_not_mass_publish: boolean;
    human_review_mandatory: boolean;
    quality_over_campaign_target?: boolean;
    checklist_does_not_approve?: boolean;
  };
  allowed_decisions: string[];
};

export type EditorialCoverage = {
  by_chapter: {
    chapter_id: string;
    chapter_name: string;
    subject_name: string;
    draft: number;
    in_review: number;
    published: number;
  }[];
  high_draft_concentration: EditorialCoverage["by_chapter"];
  mapped_but_unpublished_chapters: EditorialCoverage["by_chapter"];
  guidance: string;
};

export type EditorialCampaign = {
  targets: {
    area: string;
    subjects_included: string[];
    published: number;
    target: number;
    remaining: number;
    progress_ratio: number;
    pipeline: { draft: number; in_review: number; approved: number; changes_requested: number };
    pipeline_complete?: boolean;
    met_planning_target: boolean;
  }[];
  status_counts: {
    draft: number;
    in_review: number;
    approved: number;
    published: number;
    changes_requested: number;
    archived: number;
    missing_provenance: number;
    missing_mapping: number;
    structurally_invalid: number;
  };
  /** Phase 3.3-R1: documents which fields are COMPLETE aggregates vs SAMPLE scans. */
  count_semantics?: Record<string, string>;
  by_academic_subject: {
    subject: string;
    draft: number;
    in_review: number;
    approved: number;
    published: number;
    changes_requested: number;
    archived: number;
  }[];
  chapter_coverage: {
    chapter_id: string;
    chapter_name: string;
    subject_name: string;
    campaign_area: string | null;
    published: number;
    review_queue: number;
    draft: number;
    in_review: number;
    approved: number;
    changes_requested: number;
    concentration: "high" | "low_published" | "normal";
  }[];
  quality_metrics: {
    total_questions_scanned: number;
    sample_limit?: number;
    sample_only?: boolean;
    inventory_total_questions?: number;
    pct_with_provenance: number;
    pct_with_academic_mapping: number;
    pct_with_explanation: number;
    pct_structurally_valid: number;
    pct_reviewed_or_beyond: number;
    pct_approved_or_published: number;
    pct_published: number;
    disclaimer: string;
  };
  prioritization: string;
  rules: {
    human_review_mandatory: boolean;
    no_auto_approve: boolean;
    no_auto_publish: boolean;
    no_mass_publish_drafts: boolean;
    planning_target_only: boolean;
    biology_includes: string[];
    inventory_counts_complete?: boolean;
  };
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
  /** Optional. Narrows to CMS items whose latest-version KU lineage matches
   * ingestion.ingestion_jobs.pilot_run_id (e.g. Phase D authorized pilot). */
  pilot_run_id?: string;
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
    if (params.pilot_run_id) query.set("pilot_run_id", params.pilot_run_id);
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
  editorialReviewQueue: async (
    params: {
      status?: string;
      subject_id?: string;
      subject_name?: string;
      chapter_id?: string;
      topic_id?: string;
      difficulty?: string;
      provenance?: string;
      review_readiness?: string;
      batch_tag?: string;
      pilot_only?: boolean;
      content_type?: string;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<{ data: EditorialQueueRow[]; meta: EditorialQueueMeta }> => {
    const query = new URLSearchParams();
    if (params.status) query.set("status", params.status);
    if (params.subject_id) query.set("subject_id", params.subject_id);
    if (params.subject_name) query.set("subject_name", params.subject_name);
    if (params.chapter_id) query.set("chapter_id", params.chapter_id);
    if (params.topic_id) query.set("topic_id", params.topic_id);
    if (params.difficulty) query.set("difficulty", params.difficulty);
    if (params.provenance) query.set("provenance", params.provenance);
    if (params.review_readiness) query.set("review_readiness", params.review_readiness);
    if (params.batch_tag) query.set("batch_tag", params.batch_tag);
    if (params.pilot_only) query.set("pilot_only", "true");
    if (params.content_type) query.set("content_type", params.content_type);
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<EditorialQueueRow[]>(`/api/v1/cms/editorial-review-queue?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as EditorialQueueMeta };
  },
  reviewPacket: (id: string) => apiClient.get<ReviewPacket>(`/api/v1/cms/content-items/${id}/review-packet`),
  editorialCoverage: () => apiClient.get<EditorialCoverage>("/api/v1/cms/editorial-coverage"),
  editorialCampaign: () => apiClient.get<EditorialCampaign>("/api/v1/cms/editorial-campaign"),
  contentIntake: (params: { subject_name: string; status?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    query.set("subject_name", params.subject_name);
    if (params.status) query.set("status", params.status);
    query.set("limit", String(params.limit ?? 50));
    query.set("offset", String(params.offset ?? 0));
    return apiClient.get<{
      subject: string;
      total: number;
      intake_counts: Record<string, number>;
      items: unknown[];
      rules: Record<string, unknown>;
    }>(`/api/v1/cms/content-intake?${query.toString()}`);
  },
  batchAPilot: () => apiClient.get<BatchAPilotReport>("/api/v1/cms/editorial-batch-a-pilot"),
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
  contentReadiness: () =>
    apiClient.get<{
      content_type: string;
      status_counts: Record<string, number>;
      published: number;
      draft: number;
      in_review: number;
      approved_awaiting_publish: number;
      unmapped_concept: number;
      by_subject_status: { subject: string; status: string; count: number }[];
      chapter_imbalance?: {
        high_draft_concentration: {
          chapter_name: string;
          subject_name: string;
          draft: number;
          published: number;
        }[];
        mapped_but_unpublished_chapters: {
          chapter_name: string;
          subject_name: string;
          draft: number;
          published: number;
        }[];
        guidance: string;
      };
      quality_gates: {
        publish_requires: string[];
        never_mass_publish_drafts: boolean;
        student_visible_status: string;
      };
      campaign_notes: {
        first_target_suggestion: string;
        full_neet_mock_not_ready_below: number;
        do_not_claim_content_ready: boolean;
      };
    }>("/api/v1/cms/content-readiness"),
  publishedForConcept: async (conceptId: string, language?: string) => {
    const qs = language ? `?language=${encodeURIComponent(language)}` : "";
    const envelope = await apiClient.getFull<ContentItem[]>(`/api/v1/cms/concepts/${conceptId}/published${qs}`);
    return {
      items: envelope.data ?? [],
      language: (envelope.meta.language as string) ?? "en",
      languageFallback: Boolean(envelope.meta.language_fallback),
    };
  },
  factoryReviewDashboard: (batchId?: string) => {
    const qs = batchId ? `?batch_id=${encodeURIComponent(batchId)}` : "";
    return apiClient.get<Record<string, unknown>>(`/api/v1/cms/factory-review/dashboard${qs}`);
  },
  factoryReviewQueue: async (params: {
    batch_id?: string;
    selection_class?: string;
    needs_review?: boolean;
    sort?: string;
    limit?: number;
    offset?: number;
  } = {}) => {
    const query = new URLSearchParams();
    if (params.batch_id) query.set("batch_id", params.batch_id);
    if (params.selection_class) query.set("selection_class", params.selection_class);
    if (params.needs_review) query.set("needs_review", "true");
    if (params.sort) query.set("sort", params.sort);
    query.set("limit", String(params.limit ?? 50));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<Record<string, unknown>[]>(
      `/api/v1/cms/factory-review/queue?${query.toString()}`,
    );
    return { data: body.data ?? [], meta: body.meta as Record<string, unknown> };
  },
  factoryReviewPacket: (itemId: string) =>
    apiClient.get<Record<string, unknown>>(`/api/v1/cms/factory-review/items/${itemId}`),
  factoryReviewDecision: (
    itemId: string,
    data: {
      decision: "ACCEPT" | "CORRECTION_REQUIRED" | "REJECT";
      checklist?: Record<string, boolean>;
      failure_reasons?: string[];
      reviewer_note?: string;
    },
  ) => apiClient.post<Record<string, unknown>>(`/api/v1/cms/factory-review/items/${itemId}/decision`, data),

  humanGoldUpload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiClient.postForm<Record<string, unknown>>("/api/v1/cms/human-gold-sandbox/upload", form);
  },
  humanGoldImport: (data: { upload_id: string; session_name: string }) =>
    apiClient.post<Record<string, unknown>>("/api/v1/cms/human-gold-sandbox/import", data),
  humanGoldDashboard: (sessionId: string) =>
    apiClient.get<Record<string, unknown>>(`/api/v1/cms/human-gold-sandbox/sessions/${sessionId}/dashboard`),
  humanGoldQueue: (sessionId: string, filter = "all") =>
    apiClient.get<{ items: Record<string, unknown>[] }>(
      `/api/v1/cms/human-gold-sandbox/sessions/${sessionId}/queue?filter=${encodeURIComponent(filter)}`,
    ),
  humanGoldQuestion: (sessionId: string, questionId: string) =>
    apiClient.get<Record<string, unknown>>(
      `/api/v1/cms/human-gold-sandbox/sessions/${sessionId}/questions/${questionId}`,
    ),
  humanGoldSave: (
    sessionId: string,
    questionId: string,
    data: Record<string, unknown>,
  ) =>
    apiClient.patch<Record<string, unknown>>(
      `/api/v1/cms/human-gold-sandbox/sessions/${sessionId}/questions/${questionId}/human-review`,
      data,
    ),
  humanGoldAiCheck: (sessionId: string, batch = false) =>
    apiClient.post<Record<string, unknown>>(
      `/api/v1/cms/human-gold-sandbox/sessions/${sessionId}/ai-check?batch=${batch}`,
      {},
    ),
  humanGoldExport: (sessionId: string, fmt = "csv") =>
    apiClient.post<Record<string, unknown>>(
      `/api/v1/cms/human-gold-sandbox/sessions/${sessionId}/export?fmt=${fmt}`,
      {},
    ),
  humanGoldRunGate: (sessionId: string) =>
    apiClient.post<Record<string, unknown>>(`/api/v1/cms/human-gold-sandbox/sessions/${sessionId}/run-gate`, {}),
  humanGoldDeleteSession: (sessionId: string) =>
    apiClient.delete<Record<string, unknown>>(`/api/v1/cms/human-gold-sandbox/sessions/${sessionId}`),
};
