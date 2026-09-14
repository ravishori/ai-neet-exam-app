import type { NavSection } from "@/components/app-header";

/** Single source of truth for the student "More" navigation IA.
 *
 * Both the desktop AppHeader (via `moreSections` prop) and the mobile
 * StudentBottomNav ("More" sheet) consume this list. Adding, removing,
 * reordering, or relabeling a link should happen here and only here so
 * the two shells cannot silently drift.
 */
export const STUDENT_MORE_SECTIONS: NavSection[] = [
  {
    label: "Study tools",
    links: [
      { href: "/student/flashcards", label: "Flashcards" },
      { href: "/student/mock-tests", label: "Mock Tests" },
      { href: "/student/questions", label: "Questions" },
      { href: "/student/attempts", label: "Attempts" },
      { href: "/student/study-plan", label: "Study Plan" },
    ],
  },
  {
    label: "Account",
    links: [
      { href: "/student/profile", label: "Profile" },
      { href: "/student/settings", label: "Settings" },
    ],
  },
];

/** Flat href list — same order as the sections above. Kept for tests
 * and helpers that don't care about grouping. */
export const STUDENT_MORE_LINKS = STUDENT_MORE_SECTIONS.flatMap((s) => s.links.map((l) => ({ ...l })));
