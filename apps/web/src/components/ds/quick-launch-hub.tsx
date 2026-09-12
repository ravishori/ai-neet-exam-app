import Link from "next/link";
import { BookOpen, Brain, ClipboardList, Layers, Target, WandSparkles } from "lucide-react";

import { cn } from "@/lib/utils";

const LAUNCH_ITEMS = [
  {
    href: "/student/practice",
    label: "Practice arena",
    description: "Configure scope, then start drills",
    icon: Target,
    tone: "physics" as const,
  },
  {
    href: "/student/mock-tests",
    label: "Mock test",
    description: "Timed exam mode",
    icon: ClipboardList,
    tone: "chemistry" as const,
  },
  {
    href: "/student/questions",
    label: "Question bank",
    description: "Browse & filter PYQs",
    icon: BookOpen,
    tone: "biology" as const,
  },
  {
    href: "/student/study-plan",
    label: "Study plan",
    description: "AI weekly focus",
    icon: WandSparkles,
    tone: "ai" as const,
  },
  {
    href: "/student/flashcards",
    label: "Flashcards",
    description: "Rapid revision",
    icon: Layers,
    tone: "neutral" as const,
  },
  {
    href: "/student/analytics",
    label: "Analytics",
    description: "Score & weakness",
    icon: Brain,
    tone: "ai" as const,
  },
] as const;

const TONE_ICON: Record<(typeof LAUNCH_ITEMS)[number]["tone"], string> = {
  physics: "bg-subject-physics-muted text-subject-physics",
  chemistry: "bg-subject-chemistry-muted text-subject-chemistry",
  biology: "bg-subject-biology-muted text-subject-biology",
  ai: "ai-gradient text-white",
  neutral: "bg-muted text-foreground",
};

export function QuickLaunchHub({ className }: { className?: string }) {
  return (
    <div className={cn("grid gap-3 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {LAUNCH_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            className="hover-lift surface-glass group flex items-start gap-3 rounded-2xl p-4 outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <span
              className={cn(
                "flex size-10 shrink-0 items-center justify-center rounded-xl",
                TONE_ICON[item.tone],
              )}
            >
              <Icon className="size-5" aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block font-heading text-sm font-semibold group-hover:text-primary">{item.label}</span>
              <span className="block text-xs text-muted-foreground">{item.description}</span>
            </span>
          </Link>
        );
      })}
    </div>
  );
}
