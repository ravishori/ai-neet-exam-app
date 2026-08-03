"use client";

import { useState } from "react";
import { RotateCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";

type FlipCardProps = {
  front: string;
  back: string;
  imageUrl?: string | null;
  tags?: { label: string }[];
};

/** PR 10 — a single flashcard, front shown by default, flips to the back on
 * click/Enter/Space. Plain CSS flip (no animation library); respects
 * prefers-reduced-motion by disabling the rotation transition, not the
 * flip itself. */
export function FlipCard({ front, back, imageUrl, tags }: FlipCardProps) {
  const [flipped, setFlipped] = useState(false);

  return (
    <button
      type="button"
      onClick={() => setFlipped((f) => !f)}
      aria-pressed={flipped}
      aria-label={flipped ? "Showing answer. Press to show question." : "Showing question. Press to show answer."}
      className="group relative flex h-48 w-full flex-col justify-between rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring motion-reduce:transition-none"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {flipped ? "Answer" : "Question"}
        </span>
        <RotateCw className="size-3.5 text-muted-foreground/60" aria-hidden="true" />
      </div>

      <div className="scroll-thin flex-1 overflow-y-auto py-2 text-sm">
        {!flipped && imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt="" className="mb-2 max-h-20 w-auto rounded" />
        )}
        <p>{flipped ? back : front}</p>
      </div>

      {!!tags?.length && (
        <div className="flex flex-wrap gap-1">
          {tags.map((t) => (
            <Badge key={t.label} variant="outline" className="text-[10px]">
              {t.label}
            </Badge>
          ))}
        </div>
      )}
    </button>
  );
}
