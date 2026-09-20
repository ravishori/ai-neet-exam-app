import { STUDENT_MAIN_ID } from "@/components/ds/student-page";

/** Skip-to-main-content link — first tab stop of the student shell.
 * Hidden until focused so it does not add visible chrome, but is available
 * to any keyboard user before the header's ~9 nav-first tab stops. */
export function SkipToMain() {
  return (
    <a
      href={`#${STUDENT_MAIN_ID}`}
      data-testid="skip-to-main"
      className={
        // sr-only until keyboard-focused, then a token-styled pill in the
        // top-left of the viewport.
        "sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:left-3 focus-visible:top-3 focus-visible:z-50 " +
        "focus-visible:rounded-lg focus-visible:border focus-visible:border-ring focus-visible:bg-background focus-visible:px-3 " +
        "focus-visible:py-2 focus-visible:text-sm focus-visible:font-medium focus-visible:text-foreground " +
        "focus-visible:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
      }
    >
      Skip to main content
    </a>
  );
}
