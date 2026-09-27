/**
 * Independent visual-theme layer (Phase A-visual-themes).
 *
 * This is deliberately separate from next-themes' light/dark/system mode:
 * next-themes keeps owning `class="dark"` on <html> exactly as before, and
 * this layer only ever sets `data-app-theme="<name>"` on <html>. The two
 * compose through the same semantic CSS tokens in globals.css — neither one
 * knows the other exists.
 */

export const APP_THEMES = [
  "cosmic",
  "mint",
  "bloom",
  "electric",
  "sunset",
  "arctic",
] as const;

export type AppTheme = (typeof APP_THEMES)[number];

export const APP_THEME_LABELS: Record<AppTheme, string> = {
  cosmic: "Cosmic",
  mint: "Mint",
  bloom: "Bloom",
  electric: "Electric",
  sunset: "Sunset",
  arctic: "Arctic",
};

/** localStorage key. Absence of a stored value (or "default") means: no
 * `data-app-theme` attribute at all — the app renders its original,
 * unthemed semantic-token palette. That "no theme selected" state is a
 * first-class option, not a missing one. */
export const APP_THEME_STORAGE_KEY = "trinetra-app-theme";

export function isAppTheme(value: unknown): value is AppTheme {
  return typeof value === "string" && (APP_THEMES as readonly string[]).includes(value);
}
