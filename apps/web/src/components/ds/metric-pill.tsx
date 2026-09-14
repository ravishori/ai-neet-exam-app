import { cn } from "@/lib/utils";

type MetricPillProps = {
  label: string;
  value: string;
  className?: string;
};

/** Compact metric chip used in dashboard hero + other density-critical
 * strips where `StatCard` is too tall. Uses design-system tokens
 * (border, background, text, muted-foreground, font-mono tabular-nums)
 * so subject theming and dark mode inherit automatically. */
export function MetricPill({ label, value, className }: MetricPillProps) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-0.5 rounded-xl border border-border/50 bg-background/60 px-3 py-2 backdrop-blur-sm sm:px-3.5 sm:py-2.5",
        className,
      )}
    >
      <span className="text-[0.65rem] font-medium uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </span>
      <span className="font-mono text-base font-semibold tabular-nums tracking-tight text-foreground sm:text-lg">
        {value}
      </span>
    </div>
  );
}
