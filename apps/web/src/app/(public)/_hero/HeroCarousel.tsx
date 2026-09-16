"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { HERO_CAPABILITIES } from "./data";
import { HeroCapabilityNav } from "./HeroCapabilityNav";
import { HeroCopy } from "./HeroCopy";
import { HeroVisual } from "./HeroVisual";

/** Client orchestration. State is only the active index. Touch-swipe
 * changes it, ArrowLeft/Right too. There is intentionally NO auto-
 * advance — the brief allowed it, but every third-party study on hero
 * carousels shows autoplay depresses click-through and hurts a11y.
 * Manual only. */

const SWIPE_THRESHOLD_PX = 40;

export function HeroCarousel() {
  const [activeIndex, setActiveIndex] = useState(0);
  const touchStartX = useRef<number | null>(null);
  const active = HERO_CAPABILITIES[activeIndex];

  const select = useCallback((next: number) => {
    setActiveIndex(((next % HERO_CAPABILITIES.length) + HERO_CAPABILITIES.length) % HERO_CAPABILITIES.length);
  }, []);

  useEffect(() => {
    touchStartX.current = null;
  }, [activeIndex]);

  const onTouchStart: React.TouchEventHandler = (e) => {
    touchStartX.current = e.touches[0]?.clientX ?? null;
  };
  const onTouchEnd: React.TouchEventHandler = (e) => {
    const start = touchStartX.current;
    touchStartX.current = null;
    if (start == null) return;
    const end = e.changedTouches[0]?.clientX ?? start;
    const dx = end - start;
    if (Math.abs(dx) < SWIPE_THRESHOLD_PX) return;
    if (dx < 0) select(activeIndex + 1);
    else select(activeIndex - 1);
  };

  return (
    <section
      aria-label="What Trinetra helps you do"
      className="relative z-10 mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col gap-6 px-4 pb-16 pt-4 sm:px-6"
    >
      <div className="grid gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,520px)] md:items-center md:gap-10">
        <div className="flex flex-col gap-6">
          <HeroCopy />
          <p className="text-caption text-muted-foreground" data-testid="hero-active-copy">
            {active.copy}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href={active.href}
              className={cn(buttonVariants({ size: "lg" }), "min-h-12 px-6")}
              aria-label={`${active.ctaLabel} — ${active.title}`}
            >
              {active.ctaLabel}
            </Link>
            <Link
              href="/register"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }), "min-h-12 px-6")}
            >
              Create free account
            </Link>
          </div>
        </div>

        <div
          onTouchStart={onTouchStart}
          onTouchEnd={onTouchEnd}
          className="relative mx-auto w-full max-w-[520px]"
        >
          {HERO_CAPABILITIES.map((c, i) => (
            <div
              key={c.id}
              className={cn(
                i === activeIndex ? "relative" : "pointer-events-none absolute inset-0",
              )}
              aria-hidden={i === activeIndex ? undefined : true}
            >
              <HeroVisual capability={c} isActive={i === activeIndex} />
            </div>
          ))}
        </div>
      </div>

      <HeroCapabilityNav
        capabilities={HERO_CAPABILITIES}
        activeIndex={activeIndex}
        onSelect={select}
      />
    </section>
  );
}
