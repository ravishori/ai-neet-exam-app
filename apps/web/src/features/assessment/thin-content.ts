import { ApiError } from "@/lib/api-client";

/** Student-facing copy for expected thin published inventory (WAVE-P0-5). */
export function thinContentMessage(error: unknown): string {
  if (error instanceof ApiError && error.code === "NO_QUESTIONS_AVAILABLE") {
    return (
      error.message ||
      "No published questions are currently available for this selection. Try another topic or subject."
    );
  }
  if (error instanceof ApiError && (error.status === 401 || error.code === "UNAUTHORIZED")) {
    return "Please log in to start Practice.";
  }
  if (error instanceof ApiError && error.status >= 500) {
    return "Practice could not be loaded. Please try again.";
  }
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Something went wrong";
}

export function isNoQuestionsAvailable(error: unknown): boolean {
  return error instanceof ApiError && error.code === "NO_QUESTIONS_AVAILABLE";
}
