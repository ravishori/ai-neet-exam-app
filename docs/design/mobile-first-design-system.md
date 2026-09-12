# Mobile-first design system (student surfaces)

## Design philosophy

Serious NEET preparation: calm, academic, trustworthy. Prefer clarity over decoration. Premium ≠ heavy.

## Breakpoints

Reuse Tailwind defaults:

| Range | Token | Intent |
|-------|-------|--------|
| &lt;640px | default | Phone — bottom nav, sticky practice controls |
| ≥640px (`sm`) | tablet-ish | Inline practice controls |
| ≥1024px (`lg`) | laptop+ | Header link row, question palette sidebar |

## Typography

- Heading / UI: Plus Jakarta (`font-heading` / `font-sans`)
- Mono metrics: Geist Mono
- Practice stems: `.text-question` utility (readable measure + wrap)
- Scale utilities: `.text-display` · `.text-h1` · `.text-h2` · `.text-h3` · `.text-body` · `.text-small` · `.text-caption` · `.text-meta`

## Color tokens

Defined in `apps/web/src/app/globals.css` as CSS variables:

- Semantic: `--background`, `--foreground`, `--primary`, `--muted`, `--destructive`, `--success`, `--warning`, …
- Subject: `--subject-physics|chemistry|biology` (+ muted/border)
- AI accent: `--ai-from` / `--ai-to`
- Glass / elevation: `--glass-bg`, `--elevation-*`

Shared shells: `StudentPage`, `PageHeader`, `SectionHeader`, `StatCard` in `components/ds/`.

## Spacing & targets

- Minimum interactive height on practice CTAs/options: `--touch-target-min` (2.75rem)
- Button size `touch` on student CTAs
- Utility: `.touch-target`
- Safe area: `env(safe-area-inset-bottom)` on sticky chrome

## Navigation IA (Wave 2)

| Surface | Destinations |
|---------|----------------|
| Desktop primary | Dashboard, Practice, Subjects, Progress |
| Desktop More | Questions, Flashcards, Mocks, Attempts, Study Plan, Profile, Settings |
| Mobile bottom | Home, Practice, Subjects, Questions, Progress |

Landmarks: `Student desktop` / `Student mobile` (not duplicate “Primary”).

## Components (reuse first)

| Need | Existing |
|------|----------|
| Surfaces | `SurfaceCard` |
| Page shell / header / section / stats | `StudentPage`, `PageHeader`, `SectionHeader`, `StatCard` |
| Launch grid | `QuickLaunchHub` |
| Mobile primary nav | `StudentBottomNav` |
| Practice options | `AnswerOption` + `QuestionPanel` (+ concept practice) |
| Palette | `QuestionPalette` |
| Buttons | `Button` (shadcn / Base UI) — prefer `size="touch"` on student CTAs |

## Interaction states

Buttons/options: default · hover (pointer fine only) · focus-visible · pressed/selected · disabled · loading (`aria-busy`).

Never rely on hover alone for critical actions.

## Animation rules

- Prefer CSS (`tw-animate-css`, `animate-fade-slide-up`)
- Respect `prefers-reduced-motion`
- Exam mode (`.exam-mode`) disables glass/hover motion

## Accessibility rules

- Semantic buttons/links
- Option cards: `aria-pressed` + descriptive `aria-label`
- Live regions for practice start loading/errors
- Visible focus rings
- Named `role="progressbar"` (label on the progressbar node itself)
- Icon-only controls (account menu, theme, coach) must expose `aria-label`
- Prefer Lucide consistently — do not mix ad-hoc icon styles on student chrome

## Phase 2 token / motion notes

- Progress fill: `transition-[width] duration-300` with `motion-reduce:transition-none`
- Option selection: restrained border/ring elevation; no correctness reveal pre-submit
- Error boundaries on `/student` and attempt routes — student-facing fallback, not blank screen

## Responsive rules

1. Design phone-first.
2. Do not create separate device codebases.
3. Capability detection only when CSS is insufficient.
4. No horizontal scroll for core student flows.
5. Sticky chrome must clear safe areas and each other (coach FAB vs bottom nav).
