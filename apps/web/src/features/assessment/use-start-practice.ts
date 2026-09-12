"use client";

import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";

import { assessmentApi, type GenerateInput } from "@/features/assessment/api";
import { ApiError } from "@/lib/api-client";

export type StartPracticeInput = GenerateInput;

/**
 * Shared Practice Now / practice-arena starter.
 * Always generate → start attempt → navigate; surfaces loading + errors.
 *
 * Callers should disable the CTA while `isPending` so duplicate clicks cannot
 * enqueue a second generate+start chain.
 */
export function useStartPractice() {
  const router = useRouter();

  return useMutation({
    mutationFn: async (input: StartPracticeInput) => {
      const assessment = await assessmentApi.generatePractice(input);
      const attempt = await assessmentApi.startAttempt(assessment.id);
      return { assessment, attempt };
    },
    onSuccess: ({ attempt }) => {
      router.push(`/student/attempts/${attempt.id}`);
    },
  });
}

/** Stable test id for the dashboard hero Practice Now CTA. */
export const PRACTICE_NOW_HERO_TEST_ID = "practice-now-hero";

export function practiceStartMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "NETWORK_ERROR") {
      return "Unable to reach the practice service. Check your connection and try again.";
    }
    if (error.status === 401 || error.code === "UNAUTHORIZED" || error.code === "NOT_AUTHENTICATED") {
      return "Please log in to start Practice.";
    }
    if (error.code === "NO_QUESTIONS_AVAILABLE") {
      return (
        error.message ||
        "No published questions are currently available for this selection. Try another topic or open the practice arena."
      );
    }
    if (error.status >= 500) {
      return "Practice could not be loaded. Please try again.";
    }
    return error.message || "Unable to start practice. Please try again.";
  }
  return "Unable to start practice. Please try again.";
}
