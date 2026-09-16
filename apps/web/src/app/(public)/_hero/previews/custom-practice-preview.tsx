import { PreviewShell } from "./preview-shell";

export function CustomPracticePreview() {
  return (
    <PreviewShell theme="physics" eyebrow="Custom practice">
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "Physics", chip: "bg-subject-physics-muted text-subject-physics" },
          { label: "Chemistry", chip: "bg-subject-chemistry-muted text-subject-chemistry" },
          { label: "Biology", chip: "bg-subject-biology-muted text-subject-biology" },
        ].map((s) => (
          <div
            key={s.label}
            className={`rounded-lg px-2 py-1.5 text-center text-[0.7rem] font-medium ${s.chip}`}
          >
            {s.label}
          </div>
        ))}
      </div>
      <div className="mt-1 rounded-xl border border-border/60 bg-background/60 p-3">
        <p className="text-caption text-muted-foreground">Chapters</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {["Kinematics", "Thermodynamics", "Chemical Bonding", "Cell Biology"].map((c) => (
            <span
              key={c}
              className="rounded-full border border-border/60 bg-card px-2 py-0.5 text-[0.7rem] text-foreground"
            >
              {c}
            </span>
          ))}
        </div>
      </div>
      <div className="mt-auto flex items-center justify-between rounded-xl bg-primary/10 px-3 py-2">
        <span className="text-caption text-foreground">Question count</span>
        <span className="font-mono text-sm font-semibold tabular-nums text-primary">30</span>
      </div>
    </PreviewShell>
  );
}
