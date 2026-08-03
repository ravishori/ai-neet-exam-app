"use client";

import { useId, useState } from "react";

import type { ScorePoint } from "@/features/assessment/analytics";

const WIDTH = 480;
const HEIGHT = 160;
const PAD_X = 12;
const PAD_TOP = 16;
const PAD_BOTTOM = 24;
const GRID_VALUES = [0, 50, 100];

function yFor(score: number) {
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  return PAD_TOP + plotHeight * (1 - score / 100);
}

function xFor(index: number, count: number) {
  if (count <= 1) return WIDTH / 2;
  const plotWidth = WIDTH - PAD_X * 2;
  return PAD_X + plotWidth * (index / (count - 1));
}

/** Accuracy-over-time trend for a student's own recent attempts — a
 * single-series line, so no legend (per dataviz guidance: "a single series
 * needs no legend box"). Each point is its own hover/focus target rather
 * than a continuous crosshair, since these are a handful of discrete
 * attempts, not a dense time series. The underlying data stays reachable
 * without hovering via the existing /student/attempts history table this
 * chart links out to. `points[].score` is an accuracy percentage (0-100),
 * not the attempt's raw marks — see computeScoreTrend. */
export function ScoreTrendChart({ points }: { points: ScorePoint[] }) {
  const gradientId = useId();
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  if (points.length < 2) {
    return (
      <p className="text-sm text-muted-foreground">
        Complete a few more assessments to see your accuracy trend over time.
      </p>
    );
  }

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${xFor(i, points.length)},${yFor(p.score)}`).join(" ");
  const areaPath = `${linePath} L${xFor(points.length - 1, points.length)},${HEIGHT - PAD_BOTTOM} L${xFor(0, points.length)},${HEIGHT - PAD_BOTTOM} Z`;
  const last = points[points.length - 1];
  const active = activeIndex != null ? points[activeIndex] : null;

  return (
    <div className="flex flex-col gap-2">
      <div className="relative">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" role="img" aria-label={`Accuracy trend across your last ${points.length} attempts`}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.1" />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0" />
            </linearGradient>
          </defs>

          {GRID_VALUES.map((v) => (
            <g key={v}>
              <line x1={PAD_X} x2={WIDTH - PAD_X} y1={yFor(v)} y2={yFor(v)} stroke="var(--border)" strokeWidth="1" />
              <text x={0} y={yFor(v)} dy="0.32em" fontSize="10" fill="var(--muted-foreground)">
                {v}
              </text>
            </g>
          ))}

          <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
          <path d={linePath} fill="none" stroke="var(--chart-1)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

          {points.map((p, i) => (
            <g key={p.attemptId}>
              <circle cx={xFor(i, points.length)} cy={yFor(p.score)} r="4" fill="var(--chart-1)" stroke="var(--card)" strokeWidth="2" />
              {/* Larger, invisible hit target — the painted dot is only 8px across. */}
              <circle
                cx={xFor(i, points.length)}
                cy={yFor(p.score)}
                r="14"
                fill="transparent"
                tabIndex={0}
                role="button"
                aria-label={`${p.label}: accuracy ${p.score}%`}
                onMouseEnter={() => setActiveIndex(i)}
                onMouseLeave={() => setActiveIndex(null)}
                onFocus={() => setActiveIndex(i)}
                onBlur={() => setActiveIndex(null)}
                className="cursor-pointer outline-none focus-visible:fill-foreground/5"
              />
            </g>
          ))}

          {/* Direct-label the endpoint only, per "lines -> value at the end". */}
          <text x={xFor(points.length - 1, points.length)} y={yFor(last.score) - 10} fontSize="11" fontWeight="600" textAnchor="end" fill="var(--foreground)">
            {last.score}%
          </text>
        </svg>

        {active && (
          <div
            className="pointer-events-none absolute -translate-x-1/2 -translate-y-full rounded-md border bg-popover px-2 py-1 text-xs whitespace-nowrap text-popover-foreground shadow-sm"
            style={{
              left: `${(xFor(activeIndex!, points.length) / WIDTH) * 100}%`,
              top: `${(yFor(active.score) / HEIGHT) * 100}%`,
            }}
          >
            <span className="font-semibold">{active.score}%</span> <span className="text-muted-foreground">· {active.label}</span>
          </div>
        )}
      </div>
    </div>
  );
}
