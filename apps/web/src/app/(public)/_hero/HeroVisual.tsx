"use client";

import type { HeroCapability } from "./data";

/** Thin wrapper that swaps to the current capability's preview and
 * forwards the capability's image + priority flag. Only the first
 * capability's image should preload; the others lazy-load. */

export function HeroVisual({
  capability,
  isActive,
  priority = false,
}: {
  capability: HeroCapability;
  isActive: boolean;
  priority?: boolean;
}) {
  const Preview = capability.Preview;
  return (
    <div
      role="tabpanel"
      id={`hero-panel-${capability.id}`}
      aria-labelledby={`hero-tab-${capability.id}`}
      hidden={!isActive}
      className="motion-safe:transition-opacity motion-safe:duration-200"
    >
      <Preview
        image={{
          src: capability.imageSrc,
          alt: capability.imageAlt,
          priority,
        }}
      />
    </div>
  );
}
