import type { ComponentType } from "react";

import { CustomPracticePreview } from "./previews/custom-practice-preview";
import { MockExamPreview } from "./previews/mock-exam-preview";
import { RevisionPreview } from "./previews/revision-preview";
import { StudyCoachPreview } from "./previews/study-coach-preview";
import type { HeroPreviewProps } from "./previews/types";
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
  /** Hero art path served from `apps/web/public`. Matches the canonical
   * filenames documented in the traceability doc. */
  imageSrc: string;
  /** Descriptive scene alt-text — never the capability slogan. */
  imageAlt: string;
  /** Five concise, capability-scoped benefit lines. All describe
   * functionality currently supported by the app — no future-tense or
   * unsupported claims. Rendered as a small semantic `<ul>` under the
   * active capability's headline. */
  bullets: readonly string[];
  Preview: ComponentType<HeroPreviewProps>;
};

export const HERO_CAPABILITIES: readonly HeroCapability[] = [
  {
    id: "custom-practice",
    title: "Custom Practice",
    copy: "Practice exactly what you need.",
    href: "/student/practice",
    ctaLabel: "Start Practice",
    theme: "physics",
    imageSrc: "/images/neet/hero/neet-hero-custom-practice.webp",
    imageAlt: "Indian NEET aspirant working through a custom practice set.",
    bullets: [
      "Choose Physics, Chemistry or Biology",
      "Select chapters and topics to practise",
      "Set the number of questions",
      "Focus on concepts you want to strengthen",
      "Start a targeted practice session",
    ],
    Preview: CustomPracticePreview,
  },
  {
    id: "weekly-assessment",
    title: "Weekly Assessment",
    copy: "Know where you stand every week.",
    href: "/student/weekly-assessments",
    ctaLabel: "See This Week",
    theme: "biology",
    imageSrc: "/images/neet/hero/neet-hero-weekly-assessment.webp",
    imageAlt: "Weekly revision recap for an Indian NEET aspirant.",
    bullets: [
      "Assess your preparation across all three subjects",
      "Attempt a structured weekly assessment",
      "Review your performance after the test",
      "See which subjects the paper is weighted toward",
      "Build a consistent weekly preparation habit",
    ],
    Preview: WeeklyAssessmentPreview,
  },
  {
    id: "weak-topic-focus",
    title: "Weak Topic Focus",
    copy: "See where your preparation needs attention.",
    href: "/student/analytics",
    ctaLabel: "Open Analytics",
    theme: "chemistry",
    imageSrc: "/images/neet/hero/neet-hero-weak-topic-focus.webp",
    imageAlt: "NEET aspirant reviewing chapter-level mastery on their laptop.",
    bullets: [
      "Review your subject-wise performance",
      "See chapter-level mastery from your attempts",
      "Compare stronger and weaker areas",
      "Take the insight to your next practice session",
      "Turn performance insights into your next study action",
    ],
    Preview: WeakTopicFocusPreview,
  },
  {
    id: "revision",
    title: "Revision",
    copy: "Keep important concepts in rotation.",
    href: "/student/dashboard",
    ctaLabel: "Open Dashboard",
    theme: "neutral",
    imageSrc: "/images/neet/hero/neet-hero-revision-queue.webp",
    imageAlt: "NEET aspirant revising notebooks alongside a device.",
    bullets: [
      "See concepts and questions that need another look",
      "Revisit topics from your preparation history",
      "Keep important subjects in regular rotation",
      "Review before moving too far ahead",
      "Build revision into your preparation routine",
    ],
    Preview: RevisionPreview,
  },
  {
    id: "mock-exam",
    title: "NEET Mock",
    copy: "Prepare for the exam, not just the questions.",
    href: "/student/mock-tests",
    ctaLabel: "Take a Mock",
    theme: "physics",
    imageSrc: "/images/neet/hero/neet-hero-mock-exam.webp",
    imageAlt: "Simulated NEET-style mock exam interface for an Indian aspirant.",
    bullets: [
      "Practise with a timed exam experience",
      "Navigate questions using the question palette",
      "Mark questions for review during the attempt",
      "Track confidence while answering",
      "Review your performance after the attempt",
    ],
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
    ctaLabel: "Sign in to Open Coach",
    theme: "neutral",
    imageSrc: "/images/neet/hero/neet-hero-study-coach.webp",
    imageAlt: "NEET aspirant getting contextual help from the Study Coach.",
    bullets: [
      "Ask for help understanding difficult questions",
      "Get explanations for challenging concepts",
      "Clarify doubts while studying",
      "Use contextual guidance when you need it",
      "Learn the reasoning instead of only seeing an answer",
    ],
    Preview: StudyCoachPreview,
  },
] as const;
