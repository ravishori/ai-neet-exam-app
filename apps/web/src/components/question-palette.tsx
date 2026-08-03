"use client";

import { cn } from "@/lib/utils";

export type PaletteQuestionStatus = {
  answered: boolean;
  markedForReview: boolean;
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
    <div className={cn("grid grid-cols-6 gap-1.5 sm:grid-cols-5", className)} role="navigation" aria-label="Question palette">
      {statuses.map((status, idx) => {
        const isCurrent = idx === currentIndex;
        return (
          <button
            key={idx}
            type="button"
            onClick={() => onJump(idx)}
            aria-current={isCurrent ? "true" : undefined}
            aria-label={`Question ${idx + 1}${status.answered ? ", answered" : ", not answered"}${status.markedForReview ? ", marked for review" : ""}`}
            className={cn(
              "relative flex size-9 items-center justify-center rounded-md border text-xs font-medium tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
              isCurrent && "border-primary ring-2 ring-primary/40",
              !isCurrent && status.answered && "border-green-600/40 bg-green-50 text-green-800 dark:border-green-500/40 dark:bg-green-950 dark:text-green-300",
              !isCurrent && !status.answered && "border-border bg-transparent text-muted-foreground hover:bg-muted"
            )}
          >
            {idx + 1}
            {status.markedForReview && (
              <span
                aria-hidden="true"
                className="absolute -top-1 -right-1 size-2.5 rounded-full border border-background bg-amber-500"
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
