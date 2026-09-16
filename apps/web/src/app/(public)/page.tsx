import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { HeroCarousel } from "./_hero/HeroCarousel";

export default function LandingPage() {
  return (
    <main className="relative flex min-h-[100dvh] flex-1 flex-col overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_20%_10%,color-mix(in_oklch,var(--subject-physics)_18%,transparent),transparent_50%),radial-gradient(ellipse_at_80%_0%,color-mix(in_oklch,var(--subject-biology)_14%,transparent),transparent_45%),linear-gradient(180deg,var(--background),color-mix(in_oklch,var(--muted)_40%,var(--background)))]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35] [background-image:linear-gradient(to_right,color-mix(in_oklch,var(--foreground)_6%,transparent)_1px,transparent_1px),linear-gradient(to_bottom,color-mix(in_oklch,var(--foreground)_6%,transparent)_1px,transparent_1px)] [background-size:48px_48px] [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_75%)]"
      />

      <nav className="relative z-10 flex items-center justify-end gap-2 px-4 py-5 sm:px-6">
        <Link href="/login" className={cn(buttonVariants({ variant: "ghost" }), "min-h-11")}>
          Sign in
        </Link>
        <Link href="/register" className={cn(buttonVariants(), "min-h-11")}>
          Register
        </Link>
      </nav>

      <HeroCarousel />
    </main>
  );
}
