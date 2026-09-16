"use client";

import type { HeroCapability } from "./data";

/** Thin wrapper that swaps to the current capability's preview component.
 * Kept as its own file so the Carousel only handles state/interaction and
 * this file handles presentation. */

export function HeroVisual({
  capability,
  isActive,
}: {
  capability: HeroCapability;
  isActive: boolean;
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
      <Preview />
    </div>
  );
}
