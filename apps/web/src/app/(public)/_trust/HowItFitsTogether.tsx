import Link from "next/link";

// Deep import avoids pulling the DS barrel into the public bundle
// (the barrel re-exports AiStudyCoachShell, which drags markdown /
// highlight / katex into `/`). SurfaceCard is a small primitive on its own.
import {
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds/surface-card";

/** Server component. Mechanism-level copy only — no statistics,
 * testimonials, logos, or product claims that are not observable from
 * the current runtime. Links only to verified existing student routes;
 * cards without a verified destination render as static blocks. */

type TrustCard = {
  id: string;
  title: string;
  body: string;
  href?: string;
  linkLabel?: string;
  accent: "physics" | "chemistry" | "biology";
};

const CARDS: readonly TrustCard[] = [
  {
    id: "ncert-provenance",
    title: "Every MCQ traces to an NCERT paragraph",
    body:
      "Questions are generated and reviewed against a specific chapter, topic and concept in the NCERT taxonomy so you can always see where a question comes from.",
    accent: "physics",
  },
  {
    id: "adaptive-analytics",
    title: "Your practice adapts to your weak chapters",
    body:
      "As you attempt questions, chapter-level mastery updates so the next practice set can lean into what you've been getting wrong.",
    href: "/student/analytics",
    linkLabel: "See where you stand",
    accent: "chemistry",
  },
  {
    id: "weekly-recap",
    title: "Weekly recap, generated for you",
    body:
      "Each ISO week the platform assembles a Weekly Revision Assessment from your recent chapters plus retention practice — recommended, never forced.",
    href: "/student/weekly-assessments",
    linkLabel: "See this week",
    accent: "biology",
  },
] as const;

const ACCENT_STROKE: Record<TrustCard["accent"], string> = {
  physics: "border-subject-physics-border",
  chemistry: "border-subject-chemistry-border",
  biology: "border-subject-biology-border",
};

export function HowItFitsTogether() {
  return (
    <section
      aria-labelledby="how-it-fits-heading"
      className="relative z-10 mx-auto w-full max-w-[var(--content-max)] px-4 pb-20 pt-6 sm:px-6"
    >
      <div className="mb-6 flex flex-col gap-2">
        <p className="text-meta text-muted-foreground">How it fits together</p>
        <h2
          id="how-it-fits-heading"
          className="font-heading text-2xl font-semibold tracking-tight text-balance sm:text-3xl"
        >
          Built on three things that stay true every week.
        </h2>
      </div>
      <ul
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
        role="list"
      >
        {CARDS.map((card) => (
          <li key={card.id}>
            <SurfaceCard className={`h-full border ${ACCENT_STROKE[card.accent]}`}>
              <SurfaceCardHeader>
                <SurfaceCardTitle>{card.title}</SurfaceCardTitle>
              </SurfaceCardHeader>
              <SurfaceCardContent className="flex flex-1 flex-col gap-3">
                <SurfaceCardDescription>{card.body}</SurfaceCardDescription>
                {card.href ? (
                  <Link
                    href={card.href}
                    className="mt-auto inline-flex w-fit min-h-11 items-center gap-1 rounded-md text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                    data-testid={`trust-card-link-${card.id}`}
                  >
                    {card.linkLabel ?? "Learn more"}
                    <span aria-hidden="true">&rarr;</span>
                  </Link>
                ) : null}
              </SurfaceCardContent>
            </SurfaceCard>
          </li>
        ))}
      </ul>
    </section>
  );
}
