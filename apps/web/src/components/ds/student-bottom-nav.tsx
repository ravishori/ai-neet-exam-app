"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { BarChart3, ChevronUp, Home, Layers, MoreHorizontal, Target } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMounted } from "@/hooks/use-mounted";
import { cn } from "@/lib/utils";

const PRIMARY = [
  { href: "/student/dashboard", label: "Home", icon: Home },
  { href: "/student/practice", label: "Practice", icon: Target },
  { href: "/student/subjects", label: "Subjects", icon: Layers },
  { href: "/student/analytics", label: "Progress", icon: BarChart3 },
] as const;

/** Grouped secondary destinations — sourced from the shared IA in
 * `student-more-nav.ts` so the desktop AppHeader and this mobile
 * bottom-nav "More" sheet cannot drift. Re-exported here to keep the
 * pre-existing public import path stable for tests and callers. */
import {
  STUDENT_MORE_LINKS,
  STUDENT_MORE_SECTIONS,
} from "@/components/ds/student-more-nav";

export const MOBILE_MORE_SECTIONS = STUDENT_MORE_SECTIONS;

/** Flat list for tests / callers — same destinations, same order. */
export const MOBILE_MORE_LINKS = STUDENT_MORE_LINKS;

function isActive(pathname: string, href: string) {
  if (href === "/student/dashboard") return pathname === href;
  return pathname === href || pathname.startsWith(`${href}/`);
}

const itemClass = (active: boolean) =>
  cn(
    "relative flex min-h-[var(--touch-target-min)] w-full touch-manipulation flex-col items-center justify-center gap-0.5 rounded-md px-1",
    "text-[11px] font-medium leading-none tracking-tight outline-none",
    "transition-colors duration-150 motion-reduce:transition-none",
    "focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-1 focus-visible:ring-offset-background",
    active ? "text-primary" : "text-muted-foreground hover:text-foreground",
  );

/**
 * Compact primary navigation for phones — mirrors desktop learning path (Phase A8).
 * Hidden at `lg+` so A6/A7 desktop nav remains authoritative.
 */
export function StudentBottomNav({ className }: { className?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const mounted = useMounted();

  // Hide during live attempt runner for exam focus.
  if (pathname?.startsWith("/student/attempts/") && pathname !== "/student/attempts") {
    return null;
  }

  const moreActive = MOBILE_MORE_LINKS.some((l) => isActive(pathname, l.href));

  return (
    <nav
      aria-label="Student mobile"
      data-mobile-nav
      className={cn(
        "fixed inset-x-0 bottom-0 z-30 border-t border-glass-border bg-glass/95",
        "pb-[env(safe-area-inset-bottom)] shadow-[0_-1px_0_0_color-mix(in_oklab,var(--foreground)_4%,transparent)]",
        "backdrop-blur-md supports-[backdrop-filter]:bg-glass/85 lg:hidden",
        className,
      )}
    >
      <ul className="mx-auto grid max-w-lg grid-cols-5 gap-0 px-1.5 pt-1 pb-1">
        {PRIMARY.map((link) => {
          const Icon = link.icon;
          const active = isActive(pathname, link.href);
          return (
            <li key={link.href} className="min-w-0">
              <Link
                href={link.href}
                className={itemClass(active)}
                aria-current={active ? "page" : undefined}
                data-nav-active={active ? "true" : undefined}
              >
                {active ? (
                  <span
                    className="pointer-events-none absolute inset-x-3 top-0.5 h-0.5 rounded-full bg-primary"
                    aria-hidden="true"
                  />
                ) : null}
                <Icon
                  className={cn("size-5 shrink-0", active && "stroke-[2.25]")}
                  aria-hidden
                />
                <span className="max-w-full truncate">{link.label}</span>
              </Link>
            </li>
          );
        })}
        <li className="min-w-0">
          {mounted ? (
            <DropdownMenu>
              <DropdownMenuTrigger
                className={cn(itemClass(moreActive), "group/more")}
                aria-label="More navigation"
                aria-haspopup="menu"
                data-nav-more={moreActive ? "active" : "idle"}
              >
                {moreActive ? (
                  <span
                    className="pointer-events-none absolute inset-x-3 top-0.5 h-0.5 rounded-full bg-primary"
                    aria-hidden="true"
                  />
                ) : null}
                <MoreHorizontal
                  className={cn("size-5 shrink-0", moreActive && "stroke-[2.25]")}
                  aria-hidden
                />
                <span className="inline-flex max-w-full items-center gap-0.5 truncate">
                  More
                  <ChevronUp
                    className="size-2.5 opacity-70 transition-transform duration-150 motion-reduce:transition-none group-data-[popup-open]/more:rotate-180"
                    aria-hidden
                  />
                </span>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                side="top"
                align="end"
                className="mb-1.5 min-w-52 p-1.5"
                data-mobile-more-menu
              >
                {MOBILE_MORE_SECTIONS.map((section, idx) => (
                  <DropdownMenuGroup key={section.label}>
                    <DropdownMenuLabel className="text-meta px-2 py-1.5 tracking-[0.1em]">
                      {section.label}
                    </DropdownMenuLabel>
                    {section.links.map((link) => {
                      const active = isActive(pathname, link.href);
                      return (
                        <DropdownMenuItem
                          key={link.href}
                          className={cn(
                            "min-h-9 cursor-pointer rounded-md px-2 py-2",
                            active &&
                              "bg-primary/10 font-medium text-primary focus:bg-primary/12 focus:text-primary",
                          )}
                          aria-current={active ? "page" : undefined}
                          onClick={() => {
                            router.push(link.href);
                          }}
                        >
                          {link.label}
                        </DropdownMenuItem>
                      );
                    })}
                    {idx < MOBILE_MORE_SECTIONS.length - 1 && (
                      <DropdownMenuSeparator className="my-1.5" />
                    )}
                  </DropdownMenuGroup>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <button
              type="button"
              className={itemClass(false)}
              aria-label="More navigation"
              disabled
            >
              <MoreHorizontal className="size-5 shrink-0" aria-hidden />
              <span>More</span>
            </button>
          )}
        </li>
      </ul>
    </nav>
  );
}
