import { AppHeader, type NavSection } from "@/components/app-header";
import { AiStudyCoachShell } from "@/components/ds/ai-study-coach-shell";
import { SkipToMain } from "@/components/ds/skip-to-main";
import { StudentBottomNav } from "@/components/ds/student-bottom-nav";

/** Desktop primary — learning path (aligned with mobile bottom). */
const PRIMARY_LINKS = [
  { href: "/student/dashboard", label: "Dashboard" },
  { href: "/student/practice", label: "Practice" },
  { href: "/student/subjects", label: "Subjects" },
  { href: "/student/analytics", label: "Progress" },
];

/** Secondary More — study tools first; account links preserved (Phase A6 / A8). */
const MORE_SECTIONS: NavSection[] = [
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

export default function StudentLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="page-atmosphere flex min-h-dvh flex-1 flex-col">
      <SkipToMain />
      <AppHeader
        brandHref="/student/dashboard"
        navLabel="Student desktop"
        primaryLinks={PRIMARY_LINKS}
        moreSections={MORE_SECTIONS}
      />
      <div className="flex flex-1 flex-col">{children}</div>
      <StudentBottomNav />
      <AiStudyCoachShell />
    </div>
  );
}
