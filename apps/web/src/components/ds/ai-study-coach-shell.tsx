"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { MessageCircle, Sparkles, X } from "lucide-react";

import { AiTutorBox } from "@/components/ai-tutor-box";
import { Button } from "@/components/ui/button";
import { ConceptPicker } from "@/components/concept-picker";
import {
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
import { cn } from "@/lib/utils";

/** Dockable AI Study Coach shell — reuses existing tutor + study-plan routes. */
export function AiStudyCoachShell({ className }: { className?: string }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [conceptId, setConceptId] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const wasOpen = useRef(false);
  useEffect(() => {
    if (wasOpen.current && !open) triggerRef.current?.focus();
    wasOpen.current = open;
  }, [open]);

  // Suppress coach chrome on live attempt runners (exam-hall focus).
  if (pathname?.startsWith("/student/attempts/") && pathname !== "/student/attempts") {
    return null;
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "fixed bottom-20 right-4 z-40 flex min-h-11 items-center gap-2 rounded-full ai-gradient px-4 py-2.5 text-sm font-medium text-white shadow-lg outline-none focus-visible:ring-2 focus-visible:ring-ring/50 sm:bottom-6 sm:right-5 lg:bottom-6",
          className,
        )}
        aria-label="Open AI Study Coach"
      >
        <Sparkles className="size-4" aria-hidden />
        Study Coach
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/30 p-3 backdrop-blur-sm sm:p-4">
          <SurfaceCard
            glass
            lift={false}
            accent="none"
            className="flex h-full w-full max-w-md flex-col overflow-hidden"
            role="dialog"
            aria-modal="true"
            aria-label="AI Study Coach"
            data-testid="study-coach-dialog"
          >
            <div className="flex items-center justify-between border-b border-glass-border px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="flex size-8 items-center justify-center rounded-lg ai-gradient text-white">
                  <MessageCircle className="size-4" aria-hidden />
                </span>
                <div>
                  <p className="font-heading text-sm font-semibold">AI Study Coach</p>
                  <p className="text-xs text-muted-foreground">Doubt solver · remediation · plans</p>
                </div>
              </div>
              <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)} aria-label="Close coach">
                <X className="size-4" />
              </Button>
            </div>

            <div className="flex flex-1 flex-col gap-4 overflow-y-auto scroll-thin p-4">
              <SurfaceCardHeader className="px-0 pt-0">
                <SurfaceCardTitle className="text-sm">Concept tutor</SurfaceCardTitle>
                <SurfaceCardDescription>Pick a concept, then ask a free-text doubt.</SurfaceCardDescription>
              </SurfaceCardHeader>
              <ConceptPicker value={conceptId} onChange={setConceptId} />
              {conceptId ? (
                <AiTutorBox conceptId={conceptId} />
              ) : (
                <p className="rounded-lg border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
                  Select a concept to unlock the conversational tutor.
                </p>
              )}

              <SurfaceCardContent className="flex flex-col gap-2 border-t border-border/60 px-0 pt-4">
                <p className="text-sm font-medium">More coach tools</p>
                <Link href="/student/study-plan" className="text-sm text-primary underline-offset-2 hover:underline" onClick={() => setOpen(false)}>
                  Generate AI study plan
                </Link>
                <Link href="/student/analytics" className="text-sm text-primary underline-offset-2 hover:underline" onClick={() => setOpen(false)}>
                  Open diagnostic scorecard
                </Link>
                <Link href="/student/flashcards" className="text-sm text-primary underline-offset-2 hover:underline" onClick={() => setOpen(false)}>
                  Flashcard revision
                </Link>
              </SurfaceCardContent>
            </div>
          </SurfaceCard>
        </div>
      )}
    </>
  );
}
