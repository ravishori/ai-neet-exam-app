import { apiClient } from "@/lib/api-client";

export type Subject = { id: string; exam_id: string; code: string; name: string; display_order: number };
export type Chapter = {
  id: string;
  subject_id: string;
  code: string;
  name: string;
  display_order: number;
  neet_weightage_percent: number | null;
};
export type Topic = { id: string; chapter_id: string; code: string; name: string; display_order: number };
export type Concept = {
  id: string;
  topic_id: string;
  code: string;
  name: string;
  summary: string | null;
  ncert_reference: string | null;
  difficulty: string;
  display_order: number;
};
export type MicroCompetency = { id: string; concept_id: string; code: string; name: string; display_order: number };

export const academicApi = {
  subjects: () => apiClient.get<Subject[]>("/api/v1/subjects"),
  subject: (id: string) => apiClient.get<Subject>(`/api/v1/subjects/${id}`),
  chapters: (subjectId: string) => apiClient.get<Chapter[]>(`/api/v1/subjects/${subjectId}/chapters`),
  chapter: (id: string) => apiClient.get<Chapter>(`/api/v1/chapters/${id}`),
  topics: (chapterId: string) => apiClient.get<Topic[]>(`/api/v1/chapters/${chapterId}/topics`),
  topic: (id: string) => apiClient.get<Topic>(`/api/v1/topics/${id}`),
  concepts: (topicId: string) => apiClient.get<Concept[]>(`/api/v1/topics/${topicId}/concepts`),
  concept: (id: string) => apiClient.get<Concept>(`/api/v1/concepts/${id}`),
  microCompetencies: (conceptId: string) =>
    apiClient.get<MicroCompetency[]>(`/api/v1/concepts/${conceptId}/micro-competencies`),
  createMicroCompetency: (conceptId: string, data: { code: string; name: string; display_order?: number }) =>
    apiClient.post<MicroCompetency>(`/api/v1/concepts/${conceptId}/micro-competencies`, data),
};
