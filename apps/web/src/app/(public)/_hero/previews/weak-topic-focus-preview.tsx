import { PreviewShell } from "./preview-shell";

export function WeakTopicFocusPreview() {
  const bars = [
    { label: "Kinematics", pct: 32, theme: "bg-subject-physics" },
    { label: "Mole Concept", pct: 48, theme: "bg-subject-chemistry" },
    { label: "Human Physiology", pct: 71, theme: "bg-subject-biology" },
    { label: "Optics", pct: 22, theme: "bg-subject-physics" },
  ];
  return (
    <PreviewShell theme="chemistry" eyebrow="Where you stand">
      <div className="flex flex-col gap-2">
        {bars.map((b) => (
          <div key={b.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-caption">
              <span className="text-foreground">{b.label}</span>
              <span className="font-mono tabular-nums text-muted-foreground">{b.pct}%</span>
            </div>
            <div
              role="presentation"
              className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
            >
              <div
                className={`${b.theme} h-full rounded-full`}
                style={{ width: `${b.pct}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-auto rounded-xl border border-border/60 bg-background/60 px-3 py-2 text-caption text-muted-foreground">
        Chapter-level mastery from your attempts.
      </div>
    </PreviewShell>
  );
}
