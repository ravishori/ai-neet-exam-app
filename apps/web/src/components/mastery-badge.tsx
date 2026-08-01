import { Badge } from "@/components/ui/badge";
import type { MasteryLevel } from "@/features/learning/api";

const VARIANT_BY_LEVEL: Record<MasteryLevel, "default" | "secondary" | "outline" | "ghost"> = {
  MASTERED: "default",
  PRACTICING: "secondary",
  LEARNING: "outline",
  NOT_STARTED: "ghost",
};

const LABEL_BY_LEVEL: Record<MasteryLevel, string> = {
  MASTERED: "Mastered",
  PRACTICING: "Practicing",
  LEARNING: "Learning",
  NOT_STARTED: "Not started",
};

export function MasteryBadge({ level }: { level: MasteryLevel }) {
  return <Badge variant={VARIANT_BY_LEVEL[level]}>{LABEL_BY_LEVEL[level]}</Badge>;
}

export function MasteryBar({ score }: { score: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
    </div>
  );
}
