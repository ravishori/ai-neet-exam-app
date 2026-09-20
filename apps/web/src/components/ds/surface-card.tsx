import * as React from "react";

import { cn } from "@/lib/utils";
import { resolveSubjectTheme, SUBJECT_THEME_CLASSES, type SubjectThemeKey } from "@/components/ds/subject-theme";

/**
 * Canonical student work surface (Phase A3–A4).
 *
 * Surface levels (see globals.css):
 *   L1 solid work panel  → glass={false}  (preferred for dense content)
 *   L2 elevated chrome   → glass={true}   (header-adjacent / floating)
 *   L3 nested inset      → use .surface-l3 inside children (not this root)
 *
 * Defaults keep prior glass+lift behavior for backward compatibility.
 * Prefer glass={false} lift={false} for new dense panels.
 * Subject accents are identity only — never encode correctness.
 */
type SurfaceLevel = "l1" | "l2";

type SurfaceCardProps = React.ComponentProps<"div"> & {
  subject?: string | null;
  theme?: SubjectThemeKey;
  /** L2 glass chrome when true; L1 solid work surface when false. */
  glass?: boolean;
  lift?: boolean;
  accent?: "top" | "left" | "none";
  /** Explicit level; overrides glass mapping when set. */
  level?: SurfaceLevel;
};

export function SurfaceCard({
  className,
  subject,
  theme,
  glass = true,
  lift = true,
  accent = "left",
  level,
  children,
  ...props
}: SurfaceCardProps) {
  const key = theme ?? resolveSubjectTheme(subject);
  const tones = SUBJECT_THEME_CLASSES[key];
  const useGlass = level ? level === "l2" : glass;

  return (
    <div
      data-slot="surface-card"
      data-surface={useGlass ? "l2" : "l1"}
      className={cn(
        "relative overflow-hidden rounded-2xl text-card-foreground",
        useGlass ? "surface-l2" : "surface-l1",
        lift && "hover-lift",
        className,
      )}
      {...props}
    >
      {accent === "left" && key !== "neutral" && (
        <span aria-hidden className={cn("absolute inset-y-0 left-0 w-1", tones.accentBar)} />
      )}
      {accent === "top" && key !== "neutral" && (
        <span aria-hidden className={cn("absolute inset-x-0 top-0 h-1", tones.gradient)} />
      )}
      {children}
    </div>
  );
}

export function SurfaceCardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("flex flex-col gap-1 px-5 pt-5", className)} {...props} />;
}

export function SurfaceCardTitle({ className, ...props }: React.ComponentProps<"h3">) {
  return <h3 className={cn("text-h3 text-foreground", className)} {...props} />;
}

export function SurfaceCardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("text-body text-muted-foreground", className)} {...props} />;
}

export function SurfaceCardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("px-5 py-4", className)} {...props} />;
}
