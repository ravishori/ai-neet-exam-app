"use client";

import { cn } from "@/lib/utils";

type ReadinessGaugeProps = {
  /** 0–100 readiness index derived client-side */
  value: number;
  size?: number;
  className?: string;
  label?: string;
};

export function ReadinessGauge({ value, size = 140, className, label = "Readiness" }: ReadinessGaugeProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div className={cn("flex flex-col items-center gap-2", className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90" aria-hidden>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={stroke}
            className="text-muted"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="url(#readinessGradient)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-[stroke-dashoffset] duration-700 ease-[var(--ease-out-smooth)]"
          />
          <defs>
            <linearGradient id="readinessGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--ai-from)" />
              <stop offset="100%" stopColor="var(--ai-to)" />
            </linearGradient>
          </defs>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-3xl font-semibold tabular-nums tracking-tight">{clamped}</span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">%</span>
        </div>
      </div>
      <p className="text-sm font-medium text-muted-foreground">{label}</p>
    </div>
  );
}

/** Weighted blend of subject averages and coverage (concepts attempted / total). */
export function computeReadinessIndex(
  overview: { average_score: number; concepts_attempted: number; concepts_total: number }[],
): number {
  if (!overview.length) return 0;
  let scoreSum = 0;
  let coverageSum = 0;
  for (const s of overview) {
    scoreSum += s.average_score;
    coverageSum += s.concepts_total > 0 ? (s.concepts_attempted / s.concepts_total) * 100 : 0;
  }
  const avgScore = scoreSum / overview.length;
  const avgCoverage = coverageSum / overview.length;
  return Math.round(avgScore * 0.7 + avgCoverage * 0.3);
}
