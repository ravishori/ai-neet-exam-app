"use client";

import { cva, type VariantProps } from "class-variance-authority";
import { Check, Flag, X } from "lucide-react";

import { cn } from "@/lib/utils";

const answerOptionVariants = cva(
  "group/option relative flex touch-target min-h-[3.25rem] w-full items-start gap-3 overflow-hidden rounded-xl border p-4 text-left text-sm shadow-xs transition-[border-color,background-color,box-shadow] duration-200 touch-manipulation focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-default disabled:opacity-60 motion-reduce:transition-none",
  {
    variants: {
      state: {
        default:
          "border-border bg-card/80 hover:border-primary/40 hover:bg-muted/40 hover:shadow-sm",
        selected: "border-primary bg-primary/10 shadow-md ring-1 ring-primary/25",
        correct: "border-success bg-success/10 text-foreground",
        incorrect: "border-destructive bg-destructive/10",
        reviewed: "border-warning bg-warning/10 text-foreground",
      },
    },
    defaultVariants: { state: "default" },
  },
);

export type AnswerOptionState = NonNullable<VariantProps<typeof answerOptionVariants>["state"]>;

type AnswerOptionProps = {
  label: string;
  letter: string;
  text: string;
  state: AnswerOptionState;
  disabled?: boolean;
  onSelect: () => void;
};

export function AnswerOption({ label, letter, text, state, disabled, onSelect }: AnswerOptionProps) {
  const emphasized = state === "selected" || state === "correct" || state === "reviewed";
  return (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={state === "selected"}
      aria-invalid={state === "incorrect" ? true : undefined}
      aria-label={`Option ${label}: ${text}`}
      onClick={onSelect}
      className={cn(answerOptionVariants({ state }))}
      data-state={state}
    >
      <span
        className={cn(
          "relative z-[1] flex size-7 shrink-0 items-center justify-center rounded-lg border text-xs font-semibold tabular-nums",
          emphasized ? "border-current bg-background/80" : "border-muted-foreground/40 text-muted-foreground",
        )}
        aria-hidden="true"
      >
        {letter}
      </span>
      <span className="relative z-[1] min-w-0 flex-1 break-words pt-0.5 leading-relaxed">{text}</span>
      {state === "correct" && (
        <Check className="relative z-[1] ml-auto size-4 shrink-0 text-success" aria-hidden="true" />
      )}
      {state === "incorrect" && (
        <X className="relative z-[1] ml-auto size-4 shrink-0 text-destructive" aria-hidden="true" />
      )}
      {state === "reviewed" && (
        <Flag className="relative z-[1] ml-auto size-4 shrink-0 text-warning" aria-hidden="true" />
      )}
    </button>
  );
}

export { answerOptionVariants };
