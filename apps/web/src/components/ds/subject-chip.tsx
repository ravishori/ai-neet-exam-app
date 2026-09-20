import { cn } from "@/lib/utils";
import { resolveSubjectTheme, SUBJECT_THEME_CLASSES } from "@/components/ds/subject-theme";

export function SubjectChip({
  subject,
  className,
}: {
  subject: string;
  className?: string;
}) {
  const key = resolveSubjectTheme(subject);
  const tones = SUBJECT_THEME_CLASSES[key];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        tones.chip,
        className,
      )}
    >
      {subject}
    </span>
  );
}
