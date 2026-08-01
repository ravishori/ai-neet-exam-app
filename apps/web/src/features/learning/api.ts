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

export const learningApi = {
  conceptMastery: (conceptId: string) => apiClient.get<ConceptMastery>(`/api/v1/learning/mastery/concepts/${conceptId}`),
  topicMastery: (topicId: string) => apiClient.get<TopicMastery>(`/api/v1/learning/mastery/topics/${topicId}`),
  overview: () => apiClient.get<SubjectMasteryOverview[]>("/api/v1/learning/mastery/overview"),
};
