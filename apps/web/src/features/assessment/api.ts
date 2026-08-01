import { apiClient } from "@/lib/api-client";

export type Assessment = {
  id: string;
  assessment_type: "PRACTICE" | "MOCK";
  scope_type: "CONCEPT" | "CHAPTER" | "SUBJECT" | "FULL";
  scope_id: string | null;
  title: string;
  duration_minutes: number | null;
  marks_per_question: number;
  negative_marks_per_question: number;
  question_count: number;
};

export type AttemptSummary = {
  id: string;
  assessment_id: string;
  status: "IN_PROGRESS" | "SUBMITTED";
  started_at: string;
  submitted_at: string | null;
  score: number | null;
  correct_count: number | null;
  incorrect_count: number | null;
  skipped_count: number | null;
};

export type AttemptQuestion = {
  content_item_id: string;
  stem: string;
  options: { label: string; text: string }[];
  difficulty?: string;
  selected_option: string | null;
  correct_option?: string;
  explanation?: string;
  is_correct?: boolean | null;
};

export type AttemptDetail = AttemptSummary & {
  assessment: Assessment;
  questions: AttemptQuestion[];
};

export type GenerateInput = { scope_type: "CONCEPT" | "CHAPTER" | "SUBJECT" | "FULL"; scope_id?: string; question_count?: number };

export const assessmentApi = {
  generatePractice: (data: GenerateInput) => apiClient.post<Assessment>("/api/v1/assessments/practice", data),
  generateMock: (data: GenerateInput) => apiClient.post<Assessment>("/api/v1/assessments/mock", data),
  startAttempt: (assessmentId: string) => apiClient.post<AttemptSummary>(`/api/v1/assessments/${assessmentId}/attempts`),
  getAttempt: (attemptId: string) => apiClient.get<AttemptDetail>(`/api/v1/attempts/${attemptId}`),
  saveAnswer: (attemptId: string, data: { content_item_id: string; selected_option: string | null }) =>
    apiClient.post<{ saved: boolean }>(`/api/v1/attempts/${attemptId}/answers`, data),
  submitAttempt: (attemptId: string) => apiClient.post<AttemptSummary>(`/api/v1/attempts/${attemptId}/submit`),
  listAttempts: () => apiClient.get<AttemptSummary[]>("/api/v1/attempts"),
};
