"use client";

import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import type { HeroCapability } from "./data";

/** Mobile-portrait replacement for the six-pill tab strip. Shows exactly
 * one capability at a time with autoplay, swipe, and pagination dots.
 * Reuses the parent's `onSelect` for the actual navigation action — this
 * component only owns which item is currently DISPLAYED, never the
 * capability-selection logic itself (that stays centralized in
 * HeroCarousel, shared with the desktop HeroCapabilityNav). */

const AUTOPLAY_MS = 3500;
const RESUME_AFTER_MS = 5000;
const SWIPE_THRESHOLD_PX = 40;

export function HeroCapabilityCarouselMobile({
  capabilities,
  activeIndex,
  onSelect,
}: {
  capabilities: readonly HeroCapability[];
  activeIndex: number;
  onSelect: (nextIndex: number) => void;
}) {
  const [displayIndex, setDisplayIndex] = useState(activeIndex);
  const [paused, setPaused] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const touchStartX = useRef<number | null>(null);
  const resumeTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep the carousel's own display cursor in sync when the active
  // capability changes from elsewhere (e.g. deep-link or future
  // programmatic selection) — never duplicates the selection logic itself.
  useEffect(() => {
    setDisplayIndex(activeIndex);
  }, [activeIndex]);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const onChange = () => setReducedMotion(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    const onVisibility = () => setPaused(document.visibilityState === "hidden");
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    if (reducedMotion || paused || document.visibilityState === "hidden") return;
    const id = setInterval(() => {
      setDisplayIndex((i) => (i + 1) % capabilities.length);
    }, AUTOPLAY_MS);
    return () => clearInterval(id);
  }, [reducedMotion, paused, capabilities.length]);

  const markInteraction = () => {
    setPaused(true);
    if (resumeTimeout.current) clearTimeout(resumeTimeout.current);
    resumeTimeout.current = setTimeout(() => setPaused(false), RESUME_AFTER_MS);
  };

  useEffect(() => {
    return () => {
      if (resumeTimeout.current) clearTimeout(resumeTimeout.current);
    };
  }, []);

  const goTo = (next: number) => {
    const wrapped = ((next % capabilities.length) + capabilities.length) % capabilities.length;
    setDisplayIndex(wrapped);
    markInteraction();
  };

  const onTouchStart: React.TouchEventHandler = (e) => {
    touchStartX.current = e.touches[0]?.clientX ?? null;
    markInteraction();
  };
  const onTouchEnd: React.TouchEventHandler = (e) => {
    const start = touchStartX.current;
    touchStartX.current = null;
    if (start == null) return;
    const end = e.changedTouches[0]?.clientX ?? start;
    const dx = end - start;
    if (Math.abs(dx) < SWIPE_THRESHOLD_PX) return;
    goTo(dx < 0 ? displayIndex + 1 : displayIndex - 1);
  };

  const onKey: React.KeyboardEventHandler<HTMLDivElement> = (e) => {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      goTo(displayIndex + 1);
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      goTo(displayIndex - 1);
    }
  };

  const cap = capabilities[displayIndex];

  return (
    <div
      className="sm:hidden"
      role="region"
      aria-roledescription="carousel"
      aria-label="NEET preparation capabilities"
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
      onKeyDown={onKey}
      onPointerDown={markInteraction}
    >
      <button
        key={cap.id}
        type="button"
        aria-label={`Open ${cap.title}`}
        aria-current="true"
        onClick={() => onSelect(displayIndex)}
        className={cn(
          "flex min-h-12 w-full items-center gap-2.5 rounded-full border px-4 text-sm font-medium",
          "touch-target border-primary bg-primary text-primary-foreground",
          "motion-safe:animate-fade-in motion-reduce:animate-none",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        )}
      >
        <span className="inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-background/40 text-[0.7rem] tabular-nums">
          {displayIndex + 1}
        </span>
        <span className="truncate">{cap.title}</span>
      </button>

      <div className="mt-2 flex items-center justify-center gap-1.5" aria-hidden="true">
        {capabilities.map((c, i) => (
          <button
            key={c.id}
            type="button"
            tabIndex={-1}
            aria-hidden="true"
            onClick={() => onSelect(i)}
            className={cn(
              "h-1.5 rounded-full transition-all motion-reduce:transition-none",
              i === displayIndex ? "w-5 bg-primary" : "w-1.5 bg-border",
            )}
          />
        ))}
      </div>
    </div>
  );
}
