import { apiClient } from "@/lib/api-client";
import type { NamedRef, ScopeType } from "@/features/questions/api";

export type CertificationStatus = "VERIFIED" | "REVIEW" | "REJECTED" | null;

export type Flashcard = {
  id: string;
  front: string | null;
  back: string | null;
  image_url: string | null;
  explanation?: string | null;
  difficulty?: "easy" | "medium" | "hard" | null;
  source?: string | null;
  source_reference?: string | null;
  class_level?: string | null;
  certification_status?: CertificationStatus;
  certification_provenance?: string | null;
  tags: string[];
  language: string;
  concept: NamedRef;
  topic: NamedRef;
  chapter: NamedRef;
  subject: NamedRef;
};

export type FlashcardListParams = {
  scopeType?: ScopeType;
  scopeId?: string;
  certifiedOnly?: boolean;
  limit?: number;
  offset?: number;
};

export type FlashcardListResult = {
  data: Flashcard[];
  meta: {
    total: number;
    limit: number;
    offset: number;
    certified_only?: boolean;
    publication_gate?: {
      rejects_excluded: boolean;
      review_allowed_unless_certified_only: boolean;
    };
  };
};

export const flashcardsApi = {
  list: async (params: FlashcardListParams = {}): Promise<FlashcardListResult> => {
    const query = new URLSearchParams();
    if (params.scopeType && params.scopeId) {
      query.set("scope_type", params.scopeType);
      query.set("scope_id", params.scopeId);
    }
    if (params.certifiedOnly) {
      query.set("certified_only", "true");
    }
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<Flashcard[]>(`/api/v1/cms/flashcards?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as FlashcardListResult["meta"] };
  },
};
