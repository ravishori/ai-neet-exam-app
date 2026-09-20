import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { HeroCarousel } from "./_hero/HeroCarousel";
import { HowItFitsTogether } from "./_trust/HowItFitsTogether";

export default function LandingPage() {
  const year = new Date().getFullYear();
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

      <nav
        aria-label="Trinetra site"
        className="relative z-10 flex items-center justify-between gap-2 px-4 py-5 sm:px-6"
      >
        <Link
          href="/"
          className="group flex shrink-0 items-center gap-2.5 rounded-md py-1 pr-1 outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-1 focus-visible:ring-offset-background"
          aria-label="Trinetra home"
        >
          <span
            aria-hidden="true"
            className="flex size-8 items-center justify-center rounded-lg bg-primary text-[0.7rem] font-bold tracking-wide text-primary-foreground shadow-sm"
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
        <div className="flex items-center gap-2">
          <Link href="/login" className={cn(buttonVariants({ variant: "ghost" }), "min-h-11")}>
            Sign in
          </Link>
          <Link href="/register" className={cn(buttonVariants(), "min-h-11")}>
            Register
          </Link>
        </div>
      </nav>

      <HeroCarousel />
      <HowItFitsTogether />

      <footer
        role="contentinfo"
        className="relative z-10 mt-auto border-t border-border/60 bg-background/60"
      >
        <div className="mx-auto flex w-full max-w-[var(--content-max)] flex-col items-start justify-between gap-3 px-4 py-6 text-caption text-muted-foreground sm:flex-row sm:items-center sm:px-6">
          <p>
            <span className="font-medium text-foreground">Trinetra</span>
            {" "}&middot; NEET preparation, aligned to NCERT.
          </p>
          <nav aria-label="Legal and account" className="flex flex-wrap items-center gap-3">
            {/* Legal / contact pages don't exist yet — surfaced as inert
             * text so we neither invent URLs nor hide the intent. */}
            <span aria-disabled="true" title="Coming soon" className="cursor-default opacity-70">
              Terms
            </span>
            <span aria-disabled="true" title="Coming soon" className="cursor-default opacity-70">
              Privacy
            </span>
            <span aria-disabled="true" title="Coming soon" className="cursor-default opacity-70">
              Contact
            </span>
            <Link
              href="/login"
              className="rounded-md underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              Sign in
            </Link>
          </nav>
          <p className="tabular-nums">
            © {year} Trinetra · Designed &amp; Developed by{" "}
            <span className="font-medium text-foreground">Trinetra Digital Lab</span>
          </p>
        </div>
      </footer>
    </main>
  );
}
