"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ChevronDown, LogOut, Menu, Settings, UserCircle } from "lucide-react";

import { ThemeToggle } from "@/components/ds/theme-toggle";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout, useMe } from "@/features/auth/use-auth";
import { cn } from "@/lib/utils";

export type NavLink = { href: string; label: string };

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppHeader({
  links,
  primaryLinks,
  moreLinks = [],
}: {
  /** @deprecated prefer primaryLinks — kept for callers that pass a flat list */
  links?: NavLink[];
  primaryLinks?: NavLink[];
  moreLinks?: NavLink[];
}) {
  const { data: user } = useMe();
  const logout = useLogout();
  const router = useRouter();
  const pathname = usePathname();

  const primary = primaryLinks ?? linksFallback(links);
  const more = moreLinks;
  const allMobile = [...primary, ...more];

  return (
    <header className="sticky top-0 z-20 border-b border-glass-border bg-glass/80 backdrop-blur-xl">
      <div className="flex items-center justify-between gap-2 px-4 py-3 sm:px-6">
        <nav className="flex min-w-0 items-center gap-3 text-sm" aria-label="Primary">
          <Link href="/student/dashboard" className="font-heading text-base font-bold tracking-tight text-primary">
            Trinetra
          </Link>
          <div className="hidden items-center gap-1 lg:flex">
            {primary.map((link) => {
              const active = isActive(pathname, link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "rounded-lg px-2.5 py-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                    active && "bg-muted font-medium text-foreground",
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
            {more.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger
                  className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50"
                  aria-label="More navigation"
                >
                  More
                  <ChevronDown className="size-3.5 opacity-70" aria-hidden="true" />
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="min-w-44">
                  {more.map((link) => (
                    <DropdownMenuItem key={link.href} onClick={() => router.push(link.href)}>
                      {link.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger
              className="flex items-center justify-center rounded-md p-1.5 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 lg:hidden"
              aria-label="Open navigation menu"
            >
              <Menu className="size-5" aria-hidden="true" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-48">
              {allMobile.map((link) => (
                <DropdownMenuItem key={link.href} onClick={() => router.push(link.href)}>
                  {link.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <DropdownMenu>
            <DropdownMenuTrigger
              className="flex items-center gap-2 rounded-full px-1.5 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
              aria-label="Account menu"
            >
              <UserCircle className="size-6 text-muted-foreground" aria-hidden="true" />
              <span className="hidden max-w-36 truncate text-muted-foreground sm:inline">
                {user?.display_name ?? user?.email}
              </span>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-48">
              {user && (
                <DropdownMenuGroup>
                  <DropdownMenuLabel>{user.display_name ?? user.email}</DropdownMenuLabel>
                </DropdownMenuGroup>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => router.push("/student/profile")}>
                <UserCircle className="size-4" aria-hidden="true" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => router.push("/student/settings")}>
                <Settings className="size-4" aria-hidden="true" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                variant="destructive"
                onClick={() => logout.mutate(undefined, { onSuccess: () => router.push("/login") })}
              >
                <LogOut className="size-4" aria-hidden="true" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}

function linksFallback(links: NavLink[] | undefined): NavLink[] {
  return links ?? [];
}
