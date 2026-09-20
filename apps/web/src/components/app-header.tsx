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
import { useMounted } from "@/hooks/use-mounted";
import { cn } from "@/lib/utils";

export type NavLink = { href: string; label: string };
export type NavSection = { label: string; links: NavLink[] };

function isActive(pathname: string, href: string) {
  if (href === "/admin" || href === "/student/dashboard") {
    return pathname === href;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

const shellControlClass =
  "inline-flex touch-target touch-manipulation items-center justify-center gap-1 rounded-md px-2.5 text-sm text-muted-foreground outline-none transition-[color,background-color,border-color] duration-150 hover:bg-muted/70 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:opacity-60 motion-reduce:transition-none";

/** Desktop primary link — A7: clear active signal, quiet hover/press, no SaaS pill noise. */
const navLinkClass = (active: boolean) =>
  cn(
    "relative inline-flex h-9 items-center rounded-md px-3 text-sm tracking-tight outline-none",
    "transition-[color,background-color] duration-150 motion-reduce:transition-none",
    "hover:bg-muted/55 hover:text-foreground",
    "active:bg-muted/75",
    "focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-1 focus-visible:ring-offset-background",
    active
      ? "font-semibold text-primary"
      : "font-medium text-muted-foreground",
  );

const moreTriggerClass = (moreActive: boolean) =>
  cn(
    shellControlClass,
    "h-9 min-h-9 gap-1 border border-transparent font-medium",
    "hover:border-border/60",
    "data-popup-open:border-border/80 data-popup-open:bg-muted/80 data-popup-open:text-foreground",
    moreActive && "border-primary/30 bg-primary/8 font-semibold text-primary",
  );

const moreMenuItemClass = (active: boolean) =>
  cn(
    "min-h-9 cursor-pointer rounded-md px-2 py-2",
    active && "bg-primary/10 font-medium text-primary focus:bg-primary/12 focus:text-primary",
  );

/**
 * Global product shell header (Phase A6 brand + A7 desktop nav polish).
 * Menus mount client-side only (A12) to avoid Base UI trigger id hydration mismatches.
 */
export function AppHeader({
  links,
  primaryLinks,
  moreLinks = [],
  moreSections = [],
  brandHref = "/student/dashboard",
  navLabel = "Primary",
}: {
  /** @deprecated prefer primaryLinks — kept for callers that pass a flat list */
  links?: NavLink[];
  primaryLinks?: NavLink[];
  moreLinks?: NavLink[];
  /** Grouped secondary nav (admin / student More IA). When set, takes precedence over moreLinks. */
  moreSections?: NavSection[];
  brandHref?: string;
  navLabel?: string;
}) {
  const { data: user } = useMe();
  const logout = useLogout();
  const router = useRouter();
  const pathname = usePathname();
  const mounted = useMounted();

  const primary = primaryLinks ?? linksFallback(links);
  const sections: NavSection[] =
    moreSections.length > 0
      ? moreSections
      : moreLinks.length > 0
        ? [{ label: "More", links: moreLinks }]
        : [];
  const flatMore = sections.flatMap((s) => s.links);
  const moreActive = flatMore.some((link) => isActive(pathname, link.href));
  const allMobile = [...primary, ...flatMore];

  return (
    <header className="sticky top-0 z-20 border-b border-glass-border bg-glass/92 shadow-[0_1px_0_0_color-mix(in_oklab,var(--foreground)_4%,transparent)] backdrop-blur-md supports-[backdrop-filter]:bg-glass/80">
      <div className="mx-auto flex w-full max-w-[var(--content-max)] items-center justify-between gap-3 px-4 py-2.5 sm:px-6">
        <nav className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3" aria-label={navLabel}>
          <Link
            href={brandHref}
            className="group flex shrink-0 items-center gap-2.5 rounded-md py-1 pr-1 outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-1 focus-visible:ring-offset-background"
            aria-label="Trinetra home"
          >
            <span
              className="flex size-8 items-center justify-center rounded-lg bg-primary text-[0.7rem] font-bold tracking-wide text-primary-foreground shadow-sm"
              aria-hidden="true"
            >
              T
            </span>
            <span className="flex min-w-0 flex-col leading-none">
              <span className="font-heading text-[0.95rem] font-bold tracking-tight text-foreground sm:text-base">
                Trinetra
              </span>
              <span className="text-meta mt-0.5 hidden text-[0.625rem] tracking-[0.12em] sm:inline">
                NEET Prep
              </span>
            </span>
          </Link>

          {/* Desktop primary cluster — separated from brand; More is secondary. */}
          <ul
            data-desktop-nav
            className="ml-0.5 hidden items-center gap-0.5 border-l border-border/45 pl-3 lg:flex"
          >
            {primary.map((link) => {
              const active = isActive(pathname, link.href);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className={navLinkClass(active)}
                    aria-current={active ? "page" : undefined}
                    data-nav-active={active ? "true" : undefined}
                  >
                    {link.label}
                    {active ? (
                      <span
                        className="pointer-events-none absolute inset-x-2.5 bottom-1 h-0.5 rounded-full bg-primary"
                        aria-hidden="true"
                      />
                    ) : null}
                  </Link>
                </li>
              );
            })}

            {flatMore.length > 0 && (
              <li className="ml-0.5 flex items-center pl-1">
                <span
                  className="mr-1.5 hidden h-4 w-px bg-border/50 xl:block"
                  aria-hidden="true"
                />
                {mounted ? (
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      className={cn(moreTriggerClass(moreActive), "group/more")}
                      aria-label="More navigation"
                      aria-haspopup="menu"
                      data-nav-more={moreActive ? "active" : "idle"}
                    >
                      More
                      <ChevronDown
                        className="size-3.5 opacity-70 transition-transform duration-150 motion-reduce:transition-none group-data-[popup-open]/more:rotate-180"
                        aria-hidden="true"
                      />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent
                      align="start"
                      className="min-w-56 p-1.5"
                      data-desktop-more-menu
                    >
                      {sections.map((section, idx) => (
                        <DropdownMenuGroup key={section.label}>
                          {(sections.length > 1 || section.label !== "More") && (
                            <DropdownMenuLabel className="text-meta px-2 py-1.5 tracking-[0.1em]">
                              {section.label}
                            </DropdownMenuLabel>
                          )}
                          {section.links.map((link) => {
                            const active = isActive(pathname, link.href);
                            return (
                              <DropdownMenuItem
                                key={link.href}
                                onClick={() => {
                                  router.push(link.href);
                                }}
                                className={moreMenuItemClass(active)}
                                aria-current={active ? "page" : undefined}
                              >
                                {link.label}
                              </DropdownMenuItem>
                            );
                          })}
                          {idx < sections.length - 1 && (
                            <DropdownMenuSeparator className="my-1.5" />
                          )}
                        </DropdownMenuGroup>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : (
                  <button
                    type="button"
                    className={moreTriggerClass(false)}
                    aria-label="More navigation"
                    disabled
                  >
                    More
                    <ChevronDown className="size-3.5 opacity-70" aria-hidden="true" />
                  </button>
                )}
              </li>
            )}
          </ul>

          {mounted ? (
            <DropdownMenu>
              <DropdownMenuTrigger
                className={cn(shellControlClass, "lg:hidden")}
                aria-label="Open navigation menu"
                aria-haspopup="menu"
              >
                <Menu className="size-5" aria-hidden="true" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="min-w-56 p-1.5">
                <DropdownMenuGroup>
                  <DropdownMenuLabel className="text-meta px-2 py-1.5 tracking-[0.1em]">
                    Primary
                  </DropdownMenuLabel>
                  {primary.map((link) => {
                    const active = isActive(pathname, link.href);
                    return (
                      <DropdownMenuItem
                        key={link.href}
                        onClick={() => {
                          router.push(link.href);
                        }}
                        className={moreMenuItemClass(active)}
                        aria-current={active ? "page" : undefined}
                      >
                        {link.label}
                      </DropdownMenuItem>
                    );
                  })}
                </DropdownMenuGroup>
                {sections.map((section) => (
                  <DropdownMenuGroup key={`mobile-${section.label}`}>
                    <DropdownMenuSeparator className="my-1.5" />
                    <DropdownMenuLabel className="text-meta px-2 py-1.5 tracking-[0.1em]">
                      {section.label === "More" ? "More" : section.label}
                    </DropdownMenuLabel>
                    {section.links.map((link) => {
                      const active = isActive(pathname, link.href);
                      return (
                        <DropdownMenuItem
                          key={link.href}
                          onClick={() => {
                            router.push(link.href);
                          }}
                          className={moreMenuItemClass(active)}
                          aria-current={active ? "page" : undefined}
                        >
                          {link.label}
                        </DropdownMenuItem>
                      );
                    })}
                  </DropdownMenuGroup>
                ))}
                {sections.length === 0 &&
                  allMobile
                    .filter((link) => !primary.some((p) => p.href === link.href))
                    .map((link) => {
                      const active = isActive(pathname, link.href);
                      return (
                        <DropdownMenuItem
                          key={link.href}
                          onClick={() => {
                            router.push(link.href);
                          }}
                          className={moreMenuItemClass(active)}
                        >
                          {link.label}
                        </DropdownMenuItem>
                      );
                    })}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <button
              type="button"
              className={cn(shellControlClass, "lg:hidden")}
              aria-label="Open navigation menu"
              disabled
            >
              <Menu className="size-5" aria-hidden="true" />
            </button>
          )}
        </nav>

        <div className="flex shrink-0 items-center gap-0.5 sm:gap-1" data-shell-controls>
          <ThemeToggle />
          {mounted ? (
            <DropdownMenu>
              <DropdownMenuTrigger
                className={cn(
                  shellControlClass,
                  "group/account h-9 gap-1.5 border border-transparent px-1.5 sm:gap-2 sm:px-2",
                  "hover:border-border/60",
                  "data-popup-open:border-border/80 data-popup-open:bg-muted/80 data-popup-open:text-foreground",
                )}
                aria-label="Account menu"
                aria-haspopup="menu"
                data-account-menu-trigger
              >
                <AccountAvatar
                  displayName={user?.display_name}
                  email={user?.email}
                />
                <span
                  className="hidden max-w-36 truncate text-sm text-muted-foreground sm:inline"
                  suppressHydrationWarning
                >
                  {user?.display_name ?? user?.email}
                </span>
                <ChevronDown
                  className="hidden size-3.5 opacity-70 transition-transform duration-150 motion-reduce:transition-none group-data-[popup-open]/account:rotate-180 sm:block"
                  aria-hidden="true"
                />
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="min-w-56 p-1.5"
                data-account-menu
              >
                {user && (
                  <DropdownMenuGroup>
                    <DropdownMenuLabel className="flex items-center gap-2.5 px-2 py-2">
                      <AccountAvatar
                        displayName={user.display_name}
                        email={user.email}
                        size="md"
                      />
                      <span className="min-w-0 truncate font-medium text-foreground">
                        {user.display_name ?? user.email}
                      </span>
                    </DropdownMenuLabel>
                  </DropdownMenuGroup>
                )}
                <DropdownMenuSeparator className="my-1.5" />
                <DropdownMenuGroup>
                  <DropdownMenuLabel className="text-meta px-2 py-1.5 tracking-[0.1em]">
                    Account
                  </DropdownMenuLabel>
                  <DropdownMenuItem
                    className="min-h-9 cursor-pointer px-2 py-2"
                    onClick={() => {
                      router.push("/student/profile");
                    }}
                  >
                    <UserCircle className="size-4" aria-hidden="true" />
                    Profile
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="min-h-9 cursor-pointer px-2 py-2"
                    onClick={() => {
                      router.push("/student/settings");
                    }}
                  >
                    <Settings className="size-4" aria-hidden="true" />
                    Settings
                  </DropdownMenuItem>
                </DropdownMenuGroup>
                <DropdownMenuSeparator className="my-1.5" />
                <DropdownMenuItem
                  variant="destructive"
                  className="min-h-9 cursor-pointer px-2 py-2"
                  onClick={() =>
                    logout.mutate(undefined, { onSuccess: () => router.push("/login") })
                  }
                >
                  <LogOut className="size-4" aria-hidden="true" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <button
              type="button"
              className={cn(shellControlClass, "h-9 gap-1.5 px-1.5")}
              aria-label="Account menu"
              disabled
            >
              <span
                className="flex size-7 items-center justify-center rounded-full bg-muted text-muted-foreground ring-1 ring-border/60"
                aria-hidden="true"
              >
                <UserCircle className="size-4" />
              </span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

function linksFallback(links: NavLink[] | undefined): NavLink[] {
  return links ?? [];
}

function accountInitials(displayName?: string | null, email?: string | null) {
  const name = displayName?.trim();
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    const first = parts[0]?.[0] ?? "";
    const second = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
    return `${first}${second}`.toUpperCase() || "?";
  }
  const local = email?.trim()?.[0];
  return local ? local.toUpperCase() : "?";
}

function AccountAvatar({
  displayName,
  email,
  size = "sm",
}: {
  displayName?: string | null;
  email?: string | null;
  size?: "sm" | "md";
}) {
  const hasIdentity = Boolean(displayName?.trim() || email?.trim());
  if (!hasIdentity) {
    return (
      <span
        className={cn(
          "flex shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground ring-1 ring-border/60",
          size === "md" ? "size-8" : "size-7",
        )}
        aria-hidden="true"
      >
        <UserCircle className={size === "md" ? "size-5" : "size-4"} />
      </span>
    );
  }

  const initials = accountInitials(displayName, email);
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full bg-primary/12 font-semibold text-primary ring-1 ring-primary/15",
        size === "md" ? "size-8 text-xs" : "size-7 text-[0.65rem]",
      )}
      aria-hidden="true"
    >
      {initials}
    </span>
  );
}
