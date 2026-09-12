import * as React from "react";

import { cn } from "@/lib/utils";
import { resolveSubjectTheme, SUBJECT_THEME_CLASSES, type SubjectThemeKey } from "@/components/ds/subject-theme";

type SurfaceCardProps = React.ComponentProps<"div"> & {
  subject?: string | null;
  theme?: SubjectThemeKey;
  glass?: boolean;
  lift?: boolean;
  accent?: "top" | "left" | "none";
};

export function SurfaceCard({
  className,
  subject,
  theme,
  glass = true,
  lift = true,
  accent = "left",
  children,
  ...props
}: SurfaceCardProps) {
  const key = theme ?? resolveSubjectTheme(subject);
  const tones = SUBJECT_THEME_CLASSES[key];

  return (
    <div
      data-slot="surface-card"
      className={cn(
        "relative overflow-hidden rounded-2xl text-card-foreground",
        glass ? "surface-glass" : "bg-card shadow-md ring-1 ring-foreground/5",
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
  return <h3 className={cn("font-heading text-base font-semibold tracking-tight", className)} {...props} />;
}

export function SurfaceCardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("text-sm text-muted-foreground", className)} {...props} />;
}

export function SurfaceCardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("px-5 py-4", className)} {...props} />;
}
