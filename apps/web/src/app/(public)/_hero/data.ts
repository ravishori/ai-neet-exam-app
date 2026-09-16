import type { ComponentType } from "react";

import { CustomPracticePreview } from "./previews/custom-practice-preview";
import { MockExamPreview } from "./previews/mock-exam-preview";
import { RevisionPreview } from "./previews/revision-preview";
import { StudyCoachPreview } from "./previews/study-coach-preview";
import { WeakTopicFocusPreview } from "./previews/weak-topic-focus-preview";
import { WeeklyAssessmentPreview } from "./previews/weekly-assessment-preview";
import type { SubjectThemeKey } from "@/components/ds/subject-theme";

/** Single source of truth for the M3A homepage hero.
 *
 * `href` targets are verified against the current student route inventory.
 * Two capabilities intentionally point at broader existing surfaces because
 * dedicated pages do not exist yet (see M3A_HOMEPAGE_TRACEABILITY.md).
 */

export type HeroCapability = {
  id:
    | "custom-practice"
    | "weekly-assessment"
    | "weak-topic-focus"
    | "revision"
    | "mock-exam"
    | "study-coach";
  title: string;
  copy: string;
  href: string;
  ctaLabel: string;
  theme: SubjectThemeKey;
  /** Where the future WebP art will live. Not rendered today — placeholder
   * previews stand in until Indian aspirant imagery lands. */
  futureAssetPath: string;
  Preview: ComponentType;
};

export const HERO_CAPABILITIES: readonly HeroCapability[] = [
  {
    id: "custom-practice",
    title: "Custom Practice",
    copy: "Practice exactly what you need.",
    href: "/student/practice",
    ctaLabel: "Start practice",
    theme: "physics",
    futureAssetPath: "/images/neet/hero/neet-hero-custom-practice.webp",
    Preview: CustomPracticePreview,
  },
  {
    id: "weekly-assessment",
    title: "Weekly Assessment",
    copy: "Know where you stand every week.",
    href: "/student/weekly-assessments",
    ctaLabel: "See this week",
    theme: "biology",
    futureAssetPath: "/images/neet/hero/neet-hero-weekly-assessment.webp",
    Preview: WeeklyAssessmentPreview,
  },
  {
    id: "weak-topic-focus",
    title: "Weak Topic Focus",
    copy: "See where your preparation needs attention.",
    href: "/student/analytics",
    ctaLabel: "Open analytics",
    theme: "chemistry",
    futureAssetPath: "/images/neet/hero/neet-hero-weak-topic-focus.webp",
    Preview: WeakTopicFocusPreview,
  },
  {
    id: "revision",
    title: "Revision",
    copy: "Keep important concepts in rotation.",
    href: "/student/dashboard",
    ctaLabel: "Open dashboard",
    theme: "neutral",
    futureAssetPath: "/images/neet/hero/neet-hero-revision-queue.webp",
    Preview: RevisionPreview,
  },
  {
    id: "mock-exam",
    title: "NEET Mock",
    copy: "Prepare for the exam, not just the questions.",
    href: "/student/mock-tests",
    ctaLabel: "Take a mock",
    theme: "physics",
    futureAssetPath: "/images/neet/hero/neet-hero-mock-exam.webp",
    Preview: MockExamPreview,
  },
  {
    id: "study-coach",
    title: "Study Coach",
    copy: "Get help when you're stuck.",
    // Study Coach lives inside the authenticated student shell as a
    // dialog (AiStudyCoachShell). The public page cannot open the
    // dialog without an auth session, so we route to sign-in and let
    // the shell mount inside /student/*.
    href: "/login",
    ctaLabel: "Sign in to open Coach",
    theme: "neutral",
    futureAssetPath: "/images/neet/hero/neet-hero-study-coach.webp",
    Preview: StudyCoachPreview,
  },
] as const;
