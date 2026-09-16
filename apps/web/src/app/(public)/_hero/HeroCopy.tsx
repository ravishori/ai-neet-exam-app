/** Static copy block above the dynamic capability content.
 *
 * Renders (in order): H1 · supporting description · NCERT trust line.
 * The per-capability headline, feature bullets and CTAs are rendered by
 * HeroCarousel below this block. Single H1 for the whole page.
 */
export function HeroCopy() {
  return (
    <div className="flex flex-col items-start gap-4 text-left">
      <h1 className="font-heading text-3xl font-bold leading-[1.1] tracking-tight text-balance sm:text-4xl md:text-5xl">
        Your NEET preparation. Built around you.
      </h1>
      <p className="max-w-prose text-base leading-relaxed text-muted-foreground sm:text-lg">
        Practice what matters. Understand where you stand. Focus on what comes next.
      </p>
      <p className="text-caption text-muted-foreground">
        NCERT-aligned preparation for NEET aspirants in India.
      </p>
    </div>
  );
}
