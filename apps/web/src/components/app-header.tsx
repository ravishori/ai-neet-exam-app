"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, Settings, UserCircle } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useLogout, useMe } from "@/features/auth/use-auth";

export function AppHeader({ links }: { links: { href: string; label: string }[] }) {
  const { data: user } = useMe();
  const logout = useLogout();
  const router = useRouter();

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b bg-background/95 px-6 py-3 backdrop-blur">
      <nav className="flex items-center gap-4 text-sm">
        <span className="font-heading font-semibold text-primary">Trinetra</span>
        {links.map((link) => (
          <Link key={link.href} href={link.href} className="text-muted-foreground transition-colors hover:text-foreground">
            {link.label}
          </Link>
        ))}
      </nav>
      <DropdownMenu>
        <DropdownMenuTrigger className="flex items-center gap-2 rounded-full text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50">
          <UserCircle className="size-6 text-muted-foreground" aria-hidden="true" />
          <span className="hidden text-muted-foreground sm:inline">{user?.display_name ?? user?.email}</span>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="min-w-48">
          {user && <DropdownMenuLabel>{user.display_name ?? user.email}</DropdownMenuLabel>}
          <DropdownMenuSeparator />
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
    </header>
  );
}
