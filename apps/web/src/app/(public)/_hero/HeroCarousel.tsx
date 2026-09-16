"use client";

import Link from "next/link";
import { Check } from "lucide-react";
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
      {/* Mobile order (single column via flex + `order-*`):
       *   H1 · subcopy · trust line  →  active headline  →  visual  →
       *   bullets  →  CTAs.
       * Desktop (>=md): CSS grid — copy stack in column 1, visual
       * spans all rows in column 2, centered. Same DOM, ordering by
       * class only. */}
      <div className="flex flex-col gap-6 md:grid md:grid-cols-[minmax(0,1fr)_minmax(0,520px)] md:grid-rows-[auto_auto_auto_auto] md:items-start md:gap-x-10 md:gap-y-6">
        <div className="order-1 md:col-start-1 md:row-start-1">
          <HeroCopy />
        </div>

        <h3
          className="order-2 text-h3 text-foreground md:col-start-1 md:row-start-2"
          data-testid="hero-active-copy"
        >
          {active.copy}
        </h3>

        {/* Visual — one instance, positioned differently by breakpoint.
         * Row-spans all copy rows on desktop so it sits centered against
         * the copy stack. On mobile the flex `order-3` puts it between
         * the active headline and the bullet list per the v2.2 spec. */}
        <div
          onTouchStart={onTouchStart}
          onTouchEnd={onTouchEnd}
          className="order-3 relative mx-auto w-full max-w-[520px] md:col-start-2 md:row-start-1 md:row-span-4 md:self-center"
        >
          {HERO_CAPABILITIES.map((c, i) => (
            <div
              key={c.id}
              className={cn(
                i === activeIndex ? "relative" : "pointer-events-none absolute inset-0",
              )}
              aria-hidden={i === activeIndex ? undefined : true}
            >
              <HeroVisual capability={c} isActive={i === activeIndex} priority={i === 0} />
            </div>
          ))}
        </div>

        {/* Feature bullets. Fixed min-height keeps the CTA row from
         * jumping vertically as the active tile changes. `role="list"`
         * keeps AT semantics under Safari's list-role removal quirk.
         * `key={active.id}` remounts the list per tile change so the
         * existing `.animate-fade-in` utility (already gated by
         * prefers-reduced-motion inside globals.css) plays subtly. */}
        <ul
          key={active.id}
          role="list"
          aria-label={`${active.title} highlights`}
          data-testid="hero-bullets"
          className="order-4 flex min-h-[10.5rem] flex-col gap-1.5 text-sm motion-safe:animate-fade-in motion-reduce:animate-none sm:min-h-[9.5rem] md:col-start-1 md:row-start-3"
        >
          {active.bullets.map((bullet) => (
            <li key={bullet} className="flex items-start gap-2 leading-snug">
              <Check
                aria-hidden="true"
                className="mt-0.5 size-4 shrink-0 text-primary"
              />
              <span className="text-foreground/90">{bullet}</span>
            </li>
          ))}
        </ul>

        <div className="order-5 flex flex-wrap items-center gap-3 md:col-start-1 md:row-start-4">
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

      <HeroCapabilityNav
        capabilities={HERO_CAPABILITIES}
        activeIndex={activeIndex}
        onSelect={select}
      />

      {/* Live region — announces tab changes to screen readers. Kept
       * outside every interactive element so focus is never stolen.
       * The visible tab-change is already conveyed by aria-selected on
       * the tab and aria-controls on the panel; this narrates the swap
       * for AT users who are not sitting on the tablist. */}
      <p
        role="status"
        aria-live="polite"
        className="sr-only"
        data-testid="hero-live-announcement"
      >
        {`Now viewing: ${active.title}, tile ${activeIndex + 1} of ${HERO_CAPABILITIES.length}`}
      </p>
    </section>
  );
}
