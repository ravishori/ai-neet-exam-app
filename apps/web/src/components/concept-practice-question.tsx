"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { QuestionBody } from "@/features/cms/api";
import { cn } from "@/lib/utils";

type Props = {
  id: string;
  title?: string;
  body: QuestionBody;
};

/**
 * Concept-page practice MCQ: selectable options (radio semantics), no answer
 * leak until the student checks. Matches attempt QuestionPanel option UX.
 */
export function ConceptPracticeQuestion({ id, title = "Practice question", body }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);

  const options = body.options ?? [];
  const correct = body.correct_option;

  function onCheck() {
    if (!selected) return;
    setChecked(true);
  }

  function onTryAgain() {
    setSelected(null);
    setChecked(false);
  }

  const isCorrect = checked && selected === correct;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm leading-relaxed">{body.stem}</p>

        <fieldset className="flex flex-col gap-2" disabled={checked}>
          <legend className="sr-only">Answer options</legend>
          {options.map((o, idx) => {
            const isSelected = selected === o.label;
            const isCorrectOpt = checked && o.label === correct;
            const isWrongSelected = checked && isSelected && o.label !== correct;
            return (
              <label
                key={o.label}
                className={cn(
                  "group/option relative flex min-h-[3.25rem] cursor-pointer items-start gap-3 overflow-hidden rounded-xl border p-4 text-left text-sm shadow-xs transition-[border-color,background-color,box-shadow] touch-manipulation",
                  checked && "cursor-default",
                  isCorrectOpt && "border-green-600 bg-green-50 dark:border-green-500 dark:bg-green-950",
                  isWrongSelected && "border-destructive bg-destructive/10",
                  !checked &&
                    isSelected &&
                    "border-primary bg-primary/10 shadow-md ring-1 ring-primary/25",
                  !checked &&
                    !isSelected &&
                    "border-border bg-card/80 hover:border-primary/40 hover:bg-muted/40 hover:shadow-sm",
                )}
              >
                <input
                  type="radio"
                  name={`concept-practice-${id}`}
                  value={o.label}
                  checked={isSelected}
                  disabled={checked}
                  onChange={() => setSelected(o.label)}
                  className="sr-only"
                />
                <span
                  className={cn(
                    "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border",
                    isSelected || isCorrectOpt
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-muted-foreground/40",
                  )}
                  aria-hidden
                >
                  {(isSelected || isCorrectOpt) && (
                    <span className="size-2 rounded-full bg-primary-foreground" />
                  )}
                </span>
                <span
                  className={cn(
                    "flex size-7 shrink-0 items-center justify-center rounded-lg border text-xs font-semibold tabular-nums",
                    isSelected || isCorrectOpt
                      ? "border-current bg-background/80"
                      : "border-muted-foreground/40 text-muted-foreground",
                  )}
                  aria-hidden
                >
                  {idx < 4 ? String.fromCharCode(65 + idx) : o.label}
                </span>
                <span className="min-w-0 flex-1 break-words pt-0.5 leading-relaxed">
                  {o.text}
                </span>
                {isCorrectOpt && (
                  <Check className="ml-auto size-4 shrink-0 text-green-600 dark:text-green-400" aria-hidden />
                )}
                {isWrongSelected && (
                  <X className="ml-auto size-4 shrink-0 text-destructive" aria-hidden />
                )}
              </label>
            );
          })}
        </fieldset>

        {!checked ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" disabled={!selected} onClick={onCheck}>
              Check answer
            </Button>
            {!selected && (
              <p className="text-xs text-muted-foreground">Select an option to continue.</p>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <p
              className={cn(
                "text-sm font-medium",
                isCorrect ? "text-green-700 dark:text-green-400" : "text-destructive",
              )}
            >
              {isCorrect ? "Correct." : `Incorrect. The right answer is ${correct}.`}
            </p>
            {body.explanation && (
              <p className="text-sm text-muted-foreground">{body.explanation}</p>
            )}
            <Button type="button" variant="outline" size="sm" className="w-fit" onClick={onTryAgain}>
              Try again
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
