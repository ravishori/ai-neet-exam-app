"use client";

import { cn } from "@/lib/utils";

type AttemptLike = { started_at: string; submitted_at?: string | null };

function dayKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Last 28 days heatmap from real attempt timestamps — empty cells stay calm. */
export function StreakHeatmap({
  attempts,
  className,
}: {
  attempts: AttemptLike[] | undefined;
  className?: string;
}) {
  const counts = new Map<string, number>();
  for (const a of attempts ?? []) {
    const key = dayKey(a.submitted_at ?? a.started_at);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  const days: { key: string; count: number; label: string }[] = [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  for (let i = 27; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const key = dayKey(d.toISOString());
    days.push({
      key,
      count: counts.get(key) ?? 0,
      label: d.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    });
  }

  const activeDays = days.filter((d) => d.count > 0).length;
  const max = Math.max(1, ...days.map((d) => d.count));

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium">Activity</p>
        <p className="font-mono text-xs tabular-nums text-muted-foreground">{activeDays}/28 active days</p>
      </div>
      {attempts && attempts.length > 0 ? (
        <div className="grid grid-cols-7 gap-1.5" role="img" aria-label="Last 28 days of practice activity">
          {days.map((d) => {
            const intensity = d.count === 0 ? 0 : 0.25 + (d.count / max) * 0.75;
            return (
              <div
                key={d.key}
                title={`${d.label}: ${d.count} attempt${d.count === 1 ? "" : "s"}`}
                className="aspect-square rounded-sm ring-1 ring-foreground/5"
                style={{
                  background:
                    d.count === 0
                      ? "var(--muted)"
                      : `color-mix(in oklab, var(--ai-from) ${Math.round(intensity * 100)}%, var(--muted))`,
                }}
              />
            );
          })}
        </div>
      ) : (
        <p className="rounded-lg border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
          Complete a practice or mock to start your activity trail.
        </p>
      )}
    </div>
  );
}
