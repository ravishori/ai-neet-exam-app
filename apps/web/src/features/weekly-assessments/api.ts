import { apiClient } from "@/lib/api-client";

// Student-driven Weekly Revision recommendation — the primary MVP surface.
export type WeeklyRevisionBucket = {
  label: string;
  quota: number;
  recent_quota: number;
  previous_quota: number;
  recent_chapter_count: number;
  previous_chapter_count: number;
  weak_chapter_count: number;
  used_cold_start: boolean;
};

export type WeeklyRevisionReason = {
  cold_start?: boolean;
  buckets?: {
    label: string;
    recent_chapter_count: number;
    previous_chapter_count: number;
    weak_chapter_count: number;
    cold_start: boolean;
  }[];
  unavailable_reasons?: string[];
};

export type WeeklyRevisionStatus = "RECOMMENDED" | "IN_PROGRESS" | "COMPLETED" | "UNAVAILABLE";

export type WeeklyRevisionCurrent = {
  id: string;
  iso_year: number;
  iso_week: number;
  status: WeeklyRevisionStatus;
  estimated_duration_minutes: number;
  marks_per_question: number;
  negative_marks_per_question: number;
  attempt_limit: number;
  total_questions: number;
  generated_at: string;
  blueprint: WeeklyRevisionBucket[];
  reason: WeeklyRevisionReason;
};

export type WeeklyRevisionStart = {
  recommendation_id: string;
  assessment_id: string;
  attempt_id: string;
  duration_minutes: number;
  total_questions: number;
  status: WeeklyRevisionStatus;
};

export const weeklyRevisionsApi = {
  getCurrent: () => apiClient.get<WeeklyRevisionCurrent>("/api/v1/weekly-revisions/current"),
  startCurrent: () => apiClient.post<WeeklyRevisionStart>("/api/v1/weekly-revisions/current/attempts"),
};
