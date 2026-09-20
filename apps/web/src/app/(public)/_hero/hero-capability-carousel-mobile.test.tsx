import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HERO_CAPABILITIES } from "./data";
import { HeroCapabilityCarouselMobile } from "./HeroCapabilityCarouselMobile";

/** Direct unit coverage for the mobile carousel's autoplay/swipe/pause
 * timers — the sandboxed browser pane used for manual verification always
 * reports prefers-reduced-motion: reduce, which correctly disables
 * autoplay (per spec) but makes it impossible to visually confirm the
 * ~3.5s advance in that environment. These tests mock matchMedia to
 * simulate reduced-motion OFF so the timer path itself is verified. */

function mockMatchMedia(reducedMotion: boolean) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === "(prefers-reduced-motion: reduce)" ? reducedMotion : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

describe("HeroCapabilityCarouselMobile", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("advances to the next capability after ~3.5s when motion is not reduced", () => {
    mockMatchMedia(false);
    const onSelect = vi.fn();
    render(
      <HeroCapabilityCarouselMobile capabilities={HERO_CAPABILITIES} activeIndex={0} onSelect={onSelect} />,
    );

    expect(screen.getByRole("button", { name: /Open Custom Practice/i })).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3500);
    });

    expect(screen.getByRole("button", { name: /Open Weekly Assessment/i })).toBeInTheDocument();
  });

  it("loops from the last capability back to the first", () => {
    mockMatchMedia(false);
    const onSelect = vi.fn();
    render(
      <HeroCapabilityCarouselMobile
        capabilities={HERO_CAPABILITIES}
        activeIndex={HERO_CAPABILITIES.length - 1}
        onSelect={onSelect}
      />,
    );
    expect(screen.getByRole("button", { name: /Open Study Coach/i })).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(3500);
    });

    expect(screen.getByRole("button", { name: /Open Custom Practice/i })).toBeInTheDocument();
  });

  it("does not autoplay when prefers-reduced-motion is set", () => {
    mockMatchMedia(true);
    const onSelect = vi.fn();
    render(
      <HeroCapabilityCarouselMobile capabilities={HERO_CAPABILITIES} activeIndex={0} onSelect={onSelect} />,
    );

    act(() => {
      vi.advanceTimersByTime(10_000);
    });

    expect(screen.getByRole("button", { name: /Open Custom Practice/i })).toBeInTheDocument();
  });

  it("renders exactly six pagination dots and updates the active one", () => {
    mockMatchMedia(false);
    const onSelect = vi.fn();
    const { container } = render(
      <HeroCapabilityCarouselMobile capabilities={HERO_CAPABILITIES} activeIndex={0} onSelect={onSelect} />,
    );
    const dots = container.querySelectorAll('[aria-hidden="true"] > button');
    expect(dots).toHaveLength(6);
    expect(dots[0]?.className).toMatch(/bg-primary/);
    expect(dots[1]?.className).not.toMatch(/bg-primary/);
  });

  it("clicking the visible item calls onSelect with the displayed index", () => {
    mockMatchMedia(false);
    const onSelect = vi.fn();
    render(
      <HeroCapabilityCarouselMobile capabilities={HERO_CAPABILITIES} activeIndex={0} onSelect={onSelect} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Open Custom Practice/i }));
    expect(onSelect).toHaveBeenCalledWith(0);
  });

  it("swipe left advances, swipe right goes back", () => {
    mockMatchMedia(false);
    const onSelect = vi.fn();
    const { container } = render(
      <HeroCapabilityCarouselMobile capabilities={HERO_CAPABILITIES} activeIndex={0} onSelect={onSelect} />,
    );
    const region = container.querySelector('[role="region"]');
    expect(region).toBeTruthy();

    fireEvent.touchStart(region as Element, { touches: [{ clientX: 200 }] });
    fireEvent.touchEnd(region as Element, { changedTouches: [{ clientX: 100 }] }); // swipe left
    expect(screen.getByRole("button", { name: /Open Weekly Assessment/i })).toBeInTheDocument();

    fireEvent.touchStart(region as Element, { touches: [{ clientX: 100 }] });
    fireEvent.touchEnd(region as Element, { changedTouches: [{ clientX: 200 }] }); // swipe right
    expect(screen.getByRole("button", { name: /Open Custom Practice/i })).toBeInTheDocument();
  });

  it("pauses autoplay after user interaction and does not immediately jump", () => {
    mockMatchMedia(false);
    const onSelect = vi.fn();
    const { container } = render(
      <HeroCapabilityCarouselMobile capabilities={HERO_CAPABILITIES} activeIndex={0} onSelect={onSelect} />,
    );
    const region = container.querySelector('[role="region"]');

    fireEvent.touchStart(region as Element, { touches: [{ clientX: 200 }] });
    fireEvent.touchEnd(region as Element, { changedTouches: [{ clientX: 100 }] }); // swipe -> index 1, paused=true

    expect(screen.getByRole("button", { name: /Open Weekly Assessment/i })).toBeInTheDocument();

    // Well within the 5s resume window — autoplay must stay paused.
    act(() => {
      vi.advanceTimersByTime(3500);
    });
    expect(screen.getByRole("button", { name: /Open Weekly Assessment/i })).toBeInTheDocument();

    // After the resume idle window, autoplay resumes and advances again.
    act(() => {
      vi.advanceTimersByTime(2000); // total 5500ms since interaction -> resumed
    });
    act(() => {
      vi.advanceTimersByTime(3500); // one more autoplay tick post-resume
    });
    expect(screen.getByRole("button", { name: /Open Weak Topic Focus/i })).toBeInTheDocument();
  });
});
