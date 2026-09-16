import { PreviewShell } from "./preview-shell";
import type { HeroPreviewProps } from "./types";

export function StudyCoachPreview({ image }: HeroPreviewProps = {}) {
  return (
    <PreviewShell theme="neutral" eyebrow="Study Coach" image={image}>
      <div className="rounded-2xl border border-border/60 bg-background/60 p-3">
        <p className="text-caption text-muted-foreground">You</p>
        <p className="mt-1 text-body">Explain why entropy increases when ice melts.</p>
      </div>
      <div className="ai-gradient rounded-2xl p-[1px]">
        <div className="rounded-2xl bg-card p-3">
          <p className="text-caption text-primary">Study Coach</p>
          <p className="mt-1 text-body">
            Water molecules gain freedom of motion, so the number of accessible microstates rises —
            that increase in disorder is what raises entropy.
          </p>
        </div>
      </div>
      <div className="mt-auto flex items-center gap-2 rounded-xl bg-muted/60 px-3 py-2 text-caption text-muted-foreground">
        <span aria-hidden="true" className="inline-flex size-1.5 rounded-full bg-primary" />
        <span>Contextual to your current chapter.</span>
      </div>
    </PreviewShell>
  );
}
