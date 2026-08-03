import { apiClient } from "@/lib/api-client";
import type { NamedRef, ScopeType } from "@/features/questions/api";

export type Flashcard = {
  id: string;
  front: string | null;
  back: string | null;
  image_url: string | null;
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
  limit?: number;
  offset?: number;
};

export type FlashcardListResult = {
  data: Flashcard[];
  meta: { total: number; limit: number; offset: number };
};

export const flashcardsApi = {
  list: async (params: FlashcardListParams = {}): Promise<FlashcardListResult> => {
    const query = new URLSearchParams();
    if (params.scopeType && params.scopeId) {
      query.set("scope_type", params.scopeType);
      query.set("scope_id", params.scopeId);
    }
    query.set("limit", String(params.limit ?? 20));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<Flashcard[]>(`/api/v1/cms/flashcards?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as FlashcardListResult["meta"] };
  },
};
