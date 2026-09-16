import { PreviewShell } from "./preview-shell";

export function MockExamPreview() {
  return (
    <PreviewShell theme="physics" eyebrow="NEET mock">
      <div className="flex items-center justify-between rounded-xl border border-border/60 bg-background/60 px-3 py-2">
        <div>
          <p className="text-h3">Full mock · 180Q</p>
          <p className="text-caption text-muted-foreground">3 hours · +4 / -1</p>
        </div>
        <div className="text-right">
          <p className="text-meta text-muted-foreground">Blueprint</p>
          <p className="font-mono text-caption tabular-nums text-foreground">45 · 45 · 90</p>
        </div>
      </div>
      <div className="grid grid-cols-6 gap-1">
        {Array.from({ length: 18 }).map((_, i) => (
          <span
            key={i}
            className={`aspect-square rounded-sm ${
              i % 5 === 0 ? "bg-primary/60" : i % 3 === 0 ? "bg-primary/25" : "bg-muted"
            }`}
            aria-hidden="true"
          />
        ))}
      </div>
      <div className="mt-auto rounded-xl bg-primary/10 px-3 py-2 text-caption text-primary">
        Question palette · mark for review · timed.
      </div>
    </PreviewShell>
  );
}
