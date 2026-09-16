import Image from "next/image";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { SubjectThemeKey } from "@/components/ds/subject-theme";

/** Fixed-aspect (4:3) container for every capability preview.
 *
 * Layer order (back → front):
 *   1. `next/image` capability art, ~30% opacity, `fill`, `object-cover`
 *      (only when `image` is provided; otherwise the CSS wash is the
 *      full backdrop as before).
 *   2. Subject-theme colour wash (existing gradient).
 *   3. Existing product-preview UI card content (eyebrow row + children).
 *
 * The 4:3 shell dimensions are preserved so drop-in art cannot cause
 * layout shift. `priority` on the image is caller-controlled so only
 * the initially visible capability preloads.
 */

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
  image,
}: {
  theme: SubjectThemeKey;
  eyebrow: string;
  children: ReactNode;
  className?: string;
  image?: { src: string; alt: string; priority?: boolean };
}) {
  return (
    <div
      data-slot="hero-preview"
      data-has-image={image ? "true" : "false"}
      data-preview-placeholder={image ? undefined : "true"}
      className={cn(
        "relative isolate flex aspect-[4/3] w-full flex-col overflow-hidden rounded-3xl border border-border/60 bg-card shadow-md",
        "before:absolute before:inset-0 before:-z-10 before:rounded-3xl before:bg-gradient-to-br",
        `before:${THEME_STROKE[theme]} before:to-transparent`,
        className,
      )}
    >
      {image ? (
        <>
          <Image
            src={image.src}
            alt={image.alt}
            fill
            priority={image.priority ?? false}
            loading={image.priority ? undefined : "lazy"}
            sizes="(min-width: 1024px) 520px, (min-width: 640px) 60vw, 100vw"
            className="pointer-events-none absolute inset-0 -z-10 h-full w-full object-cover opacity-30"
          />
          {/* Readability overlay so the product card on top keeps contrast. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-background/40 via-background/60 to-background/85"
          />
        </>
      ) : null}
      <div className="relative z-10 flex items-center justify-between px-4 pt-3">
        <p className="text-meta text-muted-foreground" data-testid="hero-preview-eyebrow">
          {eyebrow}
        </p>
        <span
          aria-hidden="true"
          className="inline-flex size-2 rounded-full bg-muted-foreground/40"
        />
      </div>
      <div className="relative z-10 flex flex-1 flex-col gap-3 px-4 pb-4 pt-2">{children}</div>
    </div>
  );
}
