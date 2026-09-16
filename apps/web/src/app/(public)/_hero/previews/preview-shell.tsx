import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { SubjectThemeKey } from "@/components/ds/subject-theme";

/** Fixed-aspect container used by every capability preview. Guarantees
 * stable dimensions on the hero (no layout shift when the visual
 * swaps), and provides a subject-theme-aware placeholder frame that
 * will map cleanly onto the future WebP art when it lands. */

const THEME_STROKE: Record<SubjectThemeKey, string> = {
  physics: "from-subject-physics/25 via-subject-physics/5",
  chemistry: "from-subject-chemistry/25 via-subject-chemistry/5",
  biology: "from-subject-biology/25 via-subject-biology/5",
  neutral: "from-primary/20 via-primary/5",
};

export function PreviewShell({
  theme,
  eyebrow,
  children,
  className,
}: {
  theme: SubjectThemeKey;
  eyebrow: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      data-slot="hero-preview"
      data-preview-placeholder="true"
      className={cn(
        "relative isolate flex aspect-[4/3] w-full flex-col overflow-hidden rounded-3xl border border-border/60 bg-card shadow-md",
        // Subject-theme wash — presentation only, no correctness color leak.
        "before:absolute before:inset-0 before:-z-10 before:rounded-3xl before:bg-gradient-to-br",
        `before:${THEME_STROKE[theme]} before:to-transparent`,
        className,
      )}
    >
      <div className="flex items-center justify-between px-4 pt-3">
        <p className="text-meta text-muted-foreground" data-testid="hero-preview-eyebrow">
          {eyebrow}
        </p>
        <span
          aria-hidden="true"
          className="inline-flex size-2 rounded-full bg-muted-foreground/40"
        />
      </div>
      <div className="flex flex-1 flex-col gap-3 px-4 pb-4 pt-2">{children}</div>
    </div>
  );
}
