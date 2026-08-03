import type { AttemptQuestion, AttemptSummary } from "@/features/assessment/api";

export type TopicBreakdown = {
  topicId: string;
  topicName: string;
  correct: number;
  total: number;
  accuracyPct: number;
  avgTimeSeconds: number | null;
};

/** Per-topic accuracy for one completed attempt, weakest topic first (most
 * actionable order). Skipped questions (no answer, so is_correct is null)
 * are excluded from both the numerator and denominator — this reports
 * accuracy on attempted questions, matching how the existing attempt
 * summary already separates skipped_count from correct/incorrect_count. */
export function computeTopicBreakdown(questions: AttemptQuestion[]): TopicBreakdown[] {
  const byTopic = new Map<string, { name: string; correct: number; total: number; timeSum: number; timeCount: number }>();

  for (const q of questions) {
    if (!q.topic || q.is_correct == null) continue;
    const entry = byTopic.get(q.topic.id) ?? { name: q.topic.name, correct: 0, total: 0, timeSum: 0, timeCount: 0 };
    entry.total += 1;
    if (q.is_correct) entry.correct += 1;
    if (q.time_spent_seconds != null && q.time_spent_seconds > 0) {
      entry.timeSum += q.time_spent_seconds;
      entry.timeCount += 1;
    }
    byTopic.set(q.topic.id, entry);
  }

  return Array.from(byTopic.entries())
    .map(([topicId, e]) => ({
      topicId,
      topicName: e.name,
      correct: e.correct,
      total: e.total,
      accuracyPct: Math.round((e.correct / e.total) * 100),
      avgTimeSeconds: e.timeCount > 0 ? Math.round(e.timeSum / e.timeCount) : null,
    }))
    .sort((a, b) => a.accuracyPct - b.accuracyPct);
}

export type TimeStats = { avgSeconds: number | null; totalSeconds: number; answeredCount: number };

export function computeTimeStats(questions: AttemptQuestion[]): TimeStats {
  const times = questions.map((q) => q.time_spent_seconds).filter((t): t is number => t != null && t > 0);
  const totalSeconds = times.reduce((sum, t) => sum + t, 0);
  return {
    avgSeconds: times.length > 0 ? Math.round(totalSeconds / times.length) : null,
    totalSeconds,
    answeredCount: times.length,
  };
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder === 0 ? `${minutes}m` : `${minutes}m ${remainder}s`;
}

export type ScorePoint = { attemptId: string; label: string; score: number };

/** Accuracy-over-time trend from the student's own submitted attempts,
 * oldest to newest, capped to the most recent `limit`. Needs no new backend
 * endpoint — attempts already carry correct/incorrect_count + submitted_at.
 *
 * Plots accuracy on attempted questions (correct / (correct + incorrect)),
 * not the raw `score` field — `score` is marks (marks_per_question minus
 * negative marking for wrong answers), which varies per assessment and
 * isn't a 0-100 value, so it can't be plotted on a shared percentage axis
 * across attempts from differently-configured assessments. An attempt with
 * nothing attempted (all skipped) is excluded rather than plotted as 0%. */
export function computeScoreTrend(attempts: AttemptSummary[], limit = 10): ScorePoint[] {
  return attempts
    .filter(
      (a): a is AttemptSummary & { correct_count: number; incorrect_count: number; submitted_at: string } =>
        a.status === "SUBMITTED" &&
        a.submitted_at != null &&
        a.correct_count != null &&
        a.incorrect_count != null &&
        a.correct_count + a.incorrect_count > 0
    )
    .sort((a, b) => new Date(a.submitted_at).getTime() - new Date(b.submitted_at).getTime())
    .slice(-limit)
    .map((a) => ({
      attemptId: a.id,
      label: new Date(a.submitted_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      score: Math.round((a.correct_count / (a.correct_count + a.incorrect_count)) * 100),
    }));
}
