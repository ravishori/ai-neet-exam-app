import { apiClient } from "@/lib/api-client";

export type AssessmentTypeBreakdown = {
  assessment_type: string;
  attempts: number;
  average_score_percent: number;
};

export type AttemptsTrendPoint = { date: string; attempts: number };

export type WeakestConcept = {
  concept_id: string;
  concept_name: string;
  subject_name: string;
  attempts: number;
  correct: number;
  accuracy_percent: number;
};

export type AssessmentAnalytics = {
  total_attempts: number;
  average_score_percent: number;
  by_type: AssessmentTypeBreakdown[];
  attempts_trend: AttemptsTrendPoint[];
  weakest_concepts: WeakestConcept[];
};

export type AiAgentUsage = {
  agent_type: string;
  requests: number;
  total_cost_usd: number;
  average_latency_ms: number;
  success_rate_percent: number;
};

export type AiUsageAnalytics = {
  total_requests: number;
  total_cost_usd: number;
  fallback_rate_percent: number;
  success_rate_percent: number;
  by_agent: AiAgentUsage[];
};

export const analyticsApi = {
  assessments: () => apiClient.get<AssessmentAnalytics>("/api/v1/analytics/assessments"),
  aiUsage: () => apiClient.get<AiUsageAnalytics>("/api/v1/analytics/ai-usage"),
};
