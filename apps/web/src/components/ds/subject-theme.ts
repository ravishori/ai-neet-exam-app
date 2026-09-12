export type SubjectThemeKey = "physics" | "chemistry" | "biology" | "neutral";

const PHYSICS_ALIASES = new Set(["physics", "phy"]);
const CHEMISTRY_ALIASES = new Set(["chemistry", "chem"]);
const BIOLOGY_ALIASES = new Set(["biology", "botany", "zoology", "bio"]);

export function resolveSubjectTheme(name?: string | null): SubjectThemeKey {
  if (!name) return "neutral";
  const key = name.trim().toLowerCase();
  if (PHYSICS_ALIASES.has(key) || key.includes("physics")) return "physics";
  if (CHEMISTRY_ALIASES.has(key) || key.includes("chemistry")) return "chemistry";
  if (BIOLOGY_ALIASES.has(key) || key.includes("biology") || key.includes("botany") || key.includes("zoology")) {
    return "biology";
  }
  return "neutral";
}

export const SUBJECT_THEME_CLASSES: Record<
  SubjectThemeKey,
  {
    text: string;
    muted: string;
    border: string;
    accentBar: string;
    gradient: string;
    chip: string;
  }
> = {
  physics: {
    text: "text-subject-physics",
    muted: "bg-subject-physics-muted",
    border: "border-subject-physics-border",
    accentBar: "bg-subject-physics",
    gradient: "subject-gradient-physics",
    chip: "bg-subject-physics-muted text-subject-physics border-subject-physics-border",
  },
  chemistry: {
    text: "text-subject-chemistry",
    muted: "bg-subject-chemistry-muted",
    border: "border-subject-chemistry-border",
    accentBar: "bg-subject-chemistry",
    gradient: "subject-gradient-chemistry",
    chip: "bg-subject-chemistry-muted text-subject-chemistry border-subject-chemistry-border",
  },
  biology: {
    text: "text-subject-biology",
    muted: "bg-subject-biology-muted",
    border: "border-subject-biology-border",
    accentBar: "bg-subject-biology",
    gradient: "subject-gradient-biology",
    chip: "bg-subject-biology-muted text-subject-biology border-subject-biology-border",
  },
  neutral: {
    text: "text-primary",
    muted: "bg-muted",
    border: "border-border",
    accentBar: "bg-primary",
    gradient: "bg-primary",
    chip: "bg-muted text-muted-foreground border-border",
  },
};
