import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { SurfaceCard, SurfaceCardContent } from "@/components/ds/surface-card";

type StatCardProps = {
  label: string;
  value: ReactNode;
  hint?: string;
  className?: string;
  mono?: boolean;
};

export function StatCard({ label, value, hint, className, mono = true }: StatCardProps) {
  return (
    <SurfaceCard glass lift={false} accent="none" className={cn("min-w-0", className)}>
      <SurfaceCardContent className="flex flex-col gap-1 py-4">
        <p className="text-xs font-medium uppercase tracking-[0.1em] text-muted-foreground">{label}</p>
        <p className={cn("text-2xl font-semibold tracking-tight text-foreground", mono && "font-mono tabular-nums")}>
          {value}
        </p>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </SurfaceCardContent>
    </SurfaceCard>
  );
}
