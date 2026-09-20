"use client";

import { cn } from "@/lib/utils";
import type { HeroCapability } from "./data";

/** Tab-strip nav for the six capabilities. Keyboard: ArrowLeft/Right,
 * Home, End. Touch: buttons are >=48px tall. Screen readers: role=tab +
 * aria-selected + aria-controls. */

export function HeroCapabilityNav({
  capabilities,
  activeIndex,
  onSelect,
}: {
  capabilities: readonly HeroCapability[];
  activeIndex: number;
  onSelect: (nextIndex: number) => void;
}) {
  const onKey: React.KeyboardEventHandler<HTMLDivElement> = (e) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      onSelect((activeIndex + 1) % capabilities.length);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      onSelect((activeIndex - 1 + capabilities.length) % capabilities.length);
    } else if (e.key === "Home") {
      e.preventDefault();
      onSelect(0);
    } else if (e.key === "End") {
      e.preventDefault();
      onSelect(capabilities.length - 1);
    }
  };

  return (
    <div
      role="tablist"
      aria-label="NEET preparation capabilities"
      onKeyDown={onKey}
      className="scroll-thin -mx-2 hidden snap-x snap-mandatory gap-2 overflow-x-auto px-2 pb-1 sm:flex"
    >
      {capabilities.map((c, i) => {
        const active = i === activeIndex;
        return (
          <button
            key={c.id}
            id={`hero-tab-${c.id}`}
            type="button"
            role="tab"
            aria-selected={active}
            aria-controls={`hero-panel-${c.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onSelect(i)}
            className={cn(
              "snap-start shrink-0 rounded-full border px-4 text-sm font-medium touch-target min-h-12",
              "transition-colors motion-reduce:transition-none",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border/60 bg-card text-foreground hover:bg-muted/60",
            )}
          >
            <span className="mr-2 inline-flex size-5 items-center justify-center rounded-full bg-background/40 text-[0.7rem] tabular-nums">
              {i + 1}
            </span>
            {c.title}
          </button>
        );
      })}
    </div>
  );
}
