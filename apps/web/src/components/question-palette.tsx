"use client";

import { cn } from "@/lib/utils";

export type PaletteQuestionStatus = {
  answered: boolean;
  markedForReview: boolean;
  visited?: boolean;
};

export function QuestionPalette({
  statuses,
  currentIndex,
  onJump,
  className,
}: {
  statuses: PaletteQuestionStatus[];
  currentIndex: number;
  onJump: (index: number) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div className="grid grid-cols-6 gap-1.5 sm:grid-cols-5" role="navigation" aria-label="Question palette">
        {statuses.map((status, idx) => {
          const isCurrent = idx === currentIndex;
          const unvisited = !status.answered && !status.visited && !isCurrent;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => onJump(idx)}
              aria-current={isCurrent ? "true" : undefined}
              aria-label={`Question ${idx + 1}${status.answered ? ", answered" : ", not answered"}${status.markedForReview ? ", marked for review" : ""}${unvisited ? ", unvisited" : ""}`}
              className={cn(
                "relative flex size-9 items-center justify-center rounded-md border text-xs font-medium tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                isCurrent && "border-primary bg-primary/10 ring-2 ring-primary/40",
                !isCurrent &&
                  status.answered &&
                  "border-success/50 bg-success/10 text-foreground",
                !isCurrent &&
                  !status.answered &&
                  status.visited &&
                  "border-border bg-muted/60 text-foreground",
                !isCurrent && unvisited && "border-dashed border-border bg-transparent text-muted-foreground hover:bg-muted",
                status.markedForReview && !isCurrent && "ring-1 ring-warning/50",
              )}
            >
              {idx + 1}
              {status.markedForReview && (
                <span
                  aria-hidden="true"
                      className="absolute -top-1 -right-1 size-2.5 rounded-full border border-background bg-warning"
                />
              )}
            </button>
          );
        })}
      </div>
      <ul className="flex flex-wrap gap-3 text-[10px] uppercase tracking-wide text-muted-foreground">
        <li className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm border border-success/50 bg-success/10" /> Answered
        </li>
        <li className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm border border-border bg-muted/60" /> Visited
        </li>
        <li className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm border border-dashed border-border" /> Unvisited
        </li>
        <li className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-warning" /> Review
        </li>
      </ul>
    </div>
  );
}
