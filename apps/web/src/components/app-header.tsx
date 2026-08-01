"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useLogout, useMe } from "@/features/auth/use-auth";

export function AppHeader({ links }: { links: { href: string; label: string }[] }) {
  const { data: user } = useMe();
  const logout = useLogout();
  const router = useRouter();

  return (
    <header className="flex items-center justify-between border-b px-6 py-3">
      <nav className="flex items-center gap-4 text-sm">
        <span className="font-semibold">Trinetra</span>
        {links.map((link) => (
          <Link key={link.href} href={link.href} className="text-muted-foreground hover:text-foreground">
            {link.label}
          </Link>
        ))}
      </nav>
      <div className="flex items-center gap-3 text-sm">
        {user && <span className="text-muted-foreground">{user.display_name ?? user.email}</span>}
        <Button
          variant="outline"
          size="sm"
          onClick={() => logout.mutate(undefined, { onSuccess: () => router.push("/login") })}
        >
          Sign out
        </Button>
      </div>
    </header>
  );
}
