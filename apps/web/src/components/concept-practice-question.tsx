"use client";

import { useState } from "react";

import { AnswerOption, type AnswerOptionState } from "@/components/ds/answer-option";
import { Button } from "@/components/ui/button";
import {
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import type { QuestionBody } from "@/features/cms/api";
import { cn } from "@/lib/utils";

type Props = {
  id: string;
  title?: string;
  body: QuestionBody;
};

/**
 * Concept-page practice MCQ: selectable options, no answer leak until check.
 * Uses the shared AnswerOption primitive (same as attempt runner).
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

  function optionState(label: string): AnswerOptionState {
    if (!checked) return selected === label ? "selected" : "default";
    if (label === correct) return "correct";
    if (selected === label) return "incorrect";
    return "default";
  }

  return (
    <SurfaceCard accent="none" data-concept-practice={id}>
      <SurfaceCardHeader>
        <SurfaceCardTitle className="text-base">{title}</SurfaceCardTitle>
      </SurfaceCardHeader>
      <SurfaceCardContent className="flex flex-col gap-3">
        <p className="text-question text-foreground">{body.stem}</p>

        <div className="flex flex-col gap-2" role="group" aria-label="Answer options">
          {options.map((o, idx) => (
            <AnswerOption
              key={o.label}
              label={o.label}
              letter={idx < 4 ? String.fromCharCode(65 + idx) : o.label}
              text={o.text}
              state={optionState(o.label)}
              disabled={checked}
              onSelect={() => {
                if (!checked) setSelected(o.label);
              }}
            />
          ))}
        </div>

        {!checked ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="touch" disabled={!selected} onClick={onCheck}>
              Check answer
            </Button>
            {!selected && <p className="text-caption">Select an option to continue.</p>}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <p className={cn("text-sm font-medium", isCorrect ? "text-success" : "text-destructive")}>
              {isCorrect ? "Correct." : `Incorrect. The right answer is ${correct}.`}
            </p>
            {body.explanation && <p className="text-body text-muted-foreground">{body.explanation}</p>}
            <Button type="button" variant="outline" size="touch" className="w-fit" onClick={onTryAgain}>
              Try again
            </Button>
          </div>
        )}
      </SurfaceCardContent>
    </SurfaceCard>
  );
}
