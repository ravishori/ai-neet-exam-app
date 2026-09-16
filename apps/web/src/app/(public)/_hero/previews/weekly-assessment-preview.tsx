import { PreviewShell } from "./preview-shell";

export function WeeklyAssessmentPreview() {
  return (
    <PreviewShell theme="biology" eyebrow="Weekly assessment">
      <div className="rounded-xl border border-border/60 bg-background/60 p-3">
        <div className="flex items-center justify-between">
          <p className="text-h3">Week 38</p>
          <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[0.7rem] font-medium text-primary">
            Recommended
          </span>
        </div>
        <p className="text-caption mt-0.5 text-muted-foreground">Refreshes every ISO week</p>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[
          { label: "Physics", value: 15, chip: "text-subject-physics" },
          { label: "Chemistry", value: 15, chip: "text-subject-chemistry" },
          { label: "Biology", value: 30, chip: "text-subject-biology" },
        ].map((s) => (
          <div key={s.label} className="rounded-lg border border-border/60 bg-card p-2">
            <p className="text-meta text-muted-foreground">{s.label}</p>
            <p className={`mt-0.5 font-mono text-sm font-semibold tabular-nums ${s.chip}`}>{s.value}</p>
          </div>
        ))}
      </div>
      <div className="mt-auto flex items-center justify-between rounded-xl bg-muted/60 px-3 py-2 text-caption">
        <span>60 questions · 60 min</span>
        <span className="font-mono tabular-nums">+4 / -1</span>
      </div>
    </PreviewShell>
  );
}
