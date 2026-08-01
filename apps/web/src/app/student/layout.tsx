import { AppHeader } from "@/components/app-header";

const STUDENT_LINKS = [
  { href: "/student/dashboard", label: "Dashboard" },
  { href: "/student/profile", label: "Profile" },
  { href: "/student/settings", label: "Settings" },
];

export default function StudentLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <AppHeader links={STUDENT_LINKS} />
      {children}
    </div>
  );
}
