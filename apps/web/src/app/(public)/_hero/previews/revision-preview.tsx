import { PreviewShell } from "./preview-shell";
import type { HeroPreviewProps } from "./types";

export function RevisionPreview({ image }: HeroPreviewProps = {}) {
  return (
    <PreviewShell theme="neutral" eyebrow="Keep in rotation" image={image}>
      <div className="flex items-center justify-end">
        <span
          className="rounded-full border border-border/60 bg-background/70 px-2 py-0.5 text-[0.65rem] uppercase tracking-[0.14em] text-muted-foreground"
          aria-label="Example data — not your live rotation"
          data-testid="hero-example-chip"
        >
          Example
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {[
          { subject: "Physics", topic: "Rotational Motion", chip: "bg-subject-physics-muted text-subject-physics" },
          { subject: "Chemistry", topic: "Redox Reactions", chip: "bg-subject-chemistry-muted text-subject-chemistry" },
          { subject: "Biology", topic: "Photosynthesis", chip: "bg-subject-biology-muted text-subject-biology" },
        ].map((r) => (
          <div
            key={r.topic}
            className="flex items-center justify-between gap-2 rounded-xl border border-border/60 bg-background/60 px-3 py-2"
          >
            <div className="flex min-w-0 items-center gap-2">
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[0.7rem] font-medium ${r.chip}`}>
                {r.subject}
              </span>
              <span className="truncate text-body">{r.topic}</span>
            </div>
            <span
              aria-hidden="true"
              className="inline-block size-1.5 rounded-full bg-primary/60"
            />
          </div>
        ))}
      </div>
      <div className="mt-auto flex items-center justify-between rounded-xl bg-muted/60 px-3 py-2 text-caption">
        <span>From your recent chapters</span>
        <span className="font-mono tabular-nums text-muted-foreground">3 today</span>
      </div>
    </PreviewShell>
  );
}
