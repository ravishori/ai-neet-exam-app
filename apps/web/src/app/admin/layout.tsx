import { AppHeader } from "@/components/app-header";

const ADMIN_LINKS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/content", label: "Content" },
  { href: "/admin/coverage", label: "Coverage" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-1 flex-col">
      <AppHeader links={ADMIN_LINKS} />
      {children}
    </div>
  );
}
