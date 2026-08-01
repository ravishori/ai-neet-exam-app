import { apiClient } from "@/lib/api-client";

export type TutorAnswer = {
  answer: string;
  concept_name: string;
  ncert_reference: string | null;
  is_fallback: boolean;
  cited_published_notes: number;
};

export type GeneratedQuestion = {
  id: string;
  content_type: string;
  concept_id: string | null;
  title: string;
  slug: string;
  status: string;
  is_fallback: boolean;
};

export type StudyPlan = {
  id: string;
  target_score: number;
  current_score: number;
  exam_date: string;
  hours_per_day: number;
  plan: {
    summary: string;
    weekly_focus: string[];
    daily_schedule: { day: number; focus: string; duration_minutes: number }[];
  };
  created_at: string;
};

export const aiApi = {
  tutorExplain: (data: { concept_id: string; question: string }) =>
    apiClient.post<TutorAnswer>("/api/v1/ai/tutor/explain", data),
  generateQuestion: (data: { concept_id: string }) =>
    apiClient.post<GeneratedQuestion>("/api/v1/ai/questions/generate", data),
  generateStudyPlan: (data: { target_score: number; current_score: number; exam_date: string; hours_per_day: number }) =>
    apiClient.post<StudyPlan>("/api/v1/ai/study-plan", data),
  getStudyPlan: () => apiClient.get<StudyPlan>("/api/v1/ai/study-plan"),
};
