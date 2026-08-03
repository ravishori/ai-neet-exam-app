import { apiClient } from "@/lib/api-client";

export type MasteryLevel = "NOT_STARTED" | "LEARNING" | "PRACTICING" | "MASTERED";

export type ConceptMastery = {
  concept_id: string;
  attempts_count: number;
  correct_count: number;
  mastery_score: number;
  mastery_level: MasteryLevel;
  last_attempt_at: string | null;
};

export type TopicConceptMastery = ConceptMastery & { concept_name: string };

export type TopicMastery = {
  topic_id: string;
  average_score: number;
  concepts: TopicConceptMastery[];
};

export type SubjectMasteryOverview = {
  subject_id: string;
  subject_name: string;
  concepts_total: number;
  concepts_attempted: number;
  average_score: number;
  mastered_count: number;
};

export type RevisionDueItem = {
  concept_id: string;
  concept_name: string;
  mastery_level: MasteryLevel;
  mastery_score: number;
  next_review_at: string | null;
};

export type RecommendationReason = "due_for_revision" | "weak_concept" | "new_concept";

export type RecommendationItem = {
  concept_id: string;
  concept_name: string;
  reason: RecommendationReason;
  mastery_score: number | null;
};

export type MicroCompetencyMastery = {
  micro_competency_id: string;
  name: string;
  attempts_count: number;
  correct_count: number;
  mastery_score: number;
  mastery_level: MasteryLevel;
  last_attempt_at: string | null;
};

export const learningApi = {
  conceptMastery: (conceptId: string) => apiClient.get<ConceptMastery>(`/api/v1/learning/mastery/concepts/${conceptId}`),
  topicMastery: (topicId: string) => apiClient.get<TopicMastery>(`/api/v1/learning/mastery/topics/${topicId}`),
  overview: () => apiClient.get<SubjectMasteryOverview[]>("/api/v1/learning/mastery/overview"),
  revisionDue: () => apiClient.get<RevisionDueItem[]>("/api/v1/learning/revision/due"),
  recommendations: () => apiClient.get<RecommendationItem[]>("/api/v1/learning/recommendations"),
  microCompetencyBreakdown: (conceptId: string) =>
    apiClient.get<MicroCompetencyMastery[]>(`/api/v1/learning/mastery/concepts/${conceptId}/micro-competencies`),
  toggleBookmark: (contentItemId: string) =>
    apiClient.post<{ bookmarked: boolean }>(`/api/v1/learning/questions/${contentItemId}/bookmark/toggle`),
  getNote: (contentItemId: string) => apiClient.get<{ note_text: string | null }>(`/api/v1/learning/questions/${contentItemId}/note`),
  upsertNote: (contentItemId: string, noteText: string) =>
    apiClient.put<{ note_text: string | null }>(`/api/v1/learning/questions/${contentItemId}/note`, { note_text: noteText }),
  deleteNote: (contentItemId: string) =>
    apiClient.delete<{ note_text: string | null }>(`/api/v1/learning/questions/${contentItemId}/note`),
};
