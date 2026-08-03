import { MasteryBar } from "@/components/mastery-badge";
import { computeTimeStats, computeTopicBreakdown, formatDuration } from "@/features/assessment/analytics";
import type { AttemptQuestion } from "@/features/assessment/api";

export function TopicPerformanceBreakdown({ questions }: { questions: AttemptQuestion[] }) {
  const breakdown = computeTopicBreakdown(questions);
  const timeStats = computeTimeStats(questions);

  if (breakdown.length === 0) {
    return <p className="text-sm text-muted-foreground">No graded questions in this attempt yet.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {timeStats.avgSeconds != null && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
          <span>Avg time per question: {formatDuration(timeStats.avgSeconds)}</span>
          <span>Total time: {formatDuration(timeStats.totalSeconds)}</span>
        </div>
      )}
      <div className="flex flex-col gap-3">
        {breakdown.map((t) => (
          <div key={t.topicId} className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{t.topicName}</span>
              <span className="text-muted-foreground">
                {t.correct}/{t.total} correct · {t.accuracyPct}%
                {t.avgTimeSeconds != null && ` · avg ${formatDuration(t.avgTimeSeconds)}`}
              </span>
            </div>
            <MasteryBar score={t.accuracyPct} />
          </div>
        ))}
      </div>
    </div>
  );
}
