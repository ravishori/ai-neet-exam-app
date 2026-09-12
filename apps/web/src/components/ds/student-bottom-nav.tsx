"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, BookOpen, Home, Layers, Target } from "lucide-react";

import { cn } from "@/lib/utils";

const BOTTOM_LINKS = [
  { href: "/student/dashboard", label: "Home", icon: Home },
  { href: "/student/practice", label: "Practice", icon: Target },
  { href: "/student/subjects", label: "Subjects", icon: Layers },
  { href: "/student/questions", label: "Questions", icon: BookOpen },
  { href: "/student/analytics", label: "Progress", icon: BarChart3 },
] as const;

/** Compact primary navigation for phones — mirrors desktop learning path. */
export function StudentBottomNav({ className }: { className?: string }) {
  const pathname = usePathname();

  // Hide during live attempt runner for exam focus.
  if (pathname?.startsWith("/student/attempts/") && pathname !== "/student/attempts") {
    return null;
  }

  return (
    <nav
      aria-label="Student mobile"
      className={cn(
        "fixed inset-x-0 bottom-0 z-30 border-t border-glass-border bg-glass/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden",
        className,
      )}
    >
      <ul className="mx-auto grid max-w-lg grid-cols-5 gap-0 px-1 pt-1">
        {BOTTOM_LINKS.map((link) => {
          const Icon = link.icon;
          const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                className={cn(
                  "flex min-h-12 flex-col items-center justify-center gap-0.5 rounded-lg px-1 text-[10px] font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                  active ? "text-primary" : "text-muted-foreground",
                )}
                aria-current={active ? "page" : undefined}
              >
                <Icon className="size-5" aria-hidden />
                <span>{link.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
