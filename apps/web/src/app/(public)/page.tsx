import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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

      <nav className="relative z-10 flex items-center justify-end gap-2 px-6 py-5">
        <Link href="/login" className={cn(buttonVariants({ variant: "ghost" }), "min-h-11")}>
          Sign in
        </Link>
        <Link href="/register" className={cn(buttonVariants(), "min-h-11")}>
          Register
        </Link>
      </nav>

      <section className="relative z-10 flex flex-1 flex-col items-center justify-center gap-8 px-6 pb-24 pt-6 text-center">
        <p className="font-heading text-sm font-semibold tracking-[0.2em] text-muted-foreground uppercase animate-fade-slide-up">
          Trinetra AI Learning OS
        </p>
        <div className="flex max-w-2xl flex-col items-center gap-4 animate-fade-slide-up [animation-delay:80ms]">
          <h1 className="font-heading text-4xl font-bold tracking-tight text-balance sm:text-5xl md:text-6xl">
            NEET prep that adapts to you
          </h1>
          <p className="max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg">
            Practice published NCERT-aligned questions, track mastery, and focus where it counts.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3 animate-fade-slide-up [animation-delay:140ms]">
          <Link href="/register" className={cn(buttonVariants({ size: "lg" }), "min-h-12 px-8")}>
            Get started
          </Link>
          <Link href="/login" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "min-h-12 px-8")}>
            Sign in
          </Link>
        </div>
      </section>
    </main>
  );
}
