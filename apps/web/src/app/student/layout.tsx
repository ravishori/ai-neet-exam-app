import { AppHeader } from "@/components/app-header";
import { AiStudyCoachShell } from "@/components/ds/ai-study-coach-shell";
import { SkipToMain } from "@/components/ds/skip-to-main";
import { StudentBottomNav } from "@/components/ds/student-bottom-nav";
import { STUDENT_MORE_SECTIONS } from "@/components/ds/student-more-nav";

/** Desktop primary — learning path (aligned with mobile bottom). */
const PRIMARY_LINKS = [
  { href: "/student/dashboard", label: "Dashboard" },
  { href: "/student/practice", label: "Practice" },
  { href: "/student/subjects", label: "Subjects" },
  { href: "/student/analytics", label: "Progress" },
];

export default function StudentLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="page-atmosphere flex min-h-dvh flex-1 flex-col">
      <SkipToMain />
      <AppHeader
        brandHref="/student/dashboard"
        navLabel="Student desktop"
        primaryLinks={PRIMARY_LINKS}
        moreSections={STUDENT_MORE_SECTIONS}
      />
      <div className="flex flex-1 flex-col">{children}</div>
      <StudentBottomNav />
      <AiStudyCoachShell />
    </div>
  );
}
