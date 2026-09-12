import { AppHeader } from "@/components/app-header";
import { AiStudyCoachShell } from "@/components/ds/ai-study-coach-shell";
import { StudentBottomNav } from "@/components/ds/student-bottom-nav";

const PRIMARY_LINKS = [
  { href: "/student/dashboard", label: "Dashboard" },
  { href: "/student/practice", label: "Practice" },
  { href: "/student/questions", label: "Questions" },
  { href: "/student/analytics", label: "Analytics" },
];

const MORE_LINKS = [
  { href: "/student/subjects", label: "Subjects" },
  { href: "/student/flashcards", label: "Flashcards" },
  { href: "/student/mock-tests", label: "Mock Tests" },
  { href: "/student/attempts", label: "Attempts" },
  { href: "/student/study-plan", label: "Study Plan" },
  { href: "/student/profile", label: "Profile" },
  { href: "/student/settings", label: "Settings" },
];

export default function StudentLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="page-atmosphere flex min-h-dvh flex-1 flex-col">
      <AppHeader primaryLinks={PRIMARY_LINKS} moreLinks={MORE_LINKS} />
      <div className="flex flex-1 flex-col">{children}</div>
      <StudentBottomNav />
      <AiStudyCoachShell />
    </div>
  );
}
