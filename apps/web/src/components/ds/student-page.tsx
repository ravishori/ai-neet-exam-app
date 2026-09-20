import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type StudentPageProps = {
  children: ReactNode;
  className?: string;
  /** Max content width. Default matches most student screens. */
  width?: "sm" | "md" | "lg" | "xl";
};

const WIDTH: Record<NonNullable<StudentPageProps["width"]>, string> = {
  sm: "max-w-xl",
  md: "max-w-2xl",
  lg: "max-w-4xl",
  xl: "max-w-6xl",
};

/** DOM id the shared skip-to-main link jumps to. Exported so tests and
 * a11y tooling can address it deterministically. */
export const STUDENT_MAIN_ID = "student-main";

/** Shared student main shell: atmosphere-friendly padding, bottom-nav clearance, fade-in. */
export function StudentPage({ children, className, width = "xl" }: StudentPageProps) {
  return (
    <main
      id={STUDENT_MAIN_ID}
      // tabIndex=-1 lets Skip-to-Main move focus here without inserting the
      // main into the natural tab order.
      tabIndex={-1}
      className={cn(
        // Keep pb-24 through sm/md so fixed mobile bottom nav never covers content;
        // lg+ drops to pb-10 when StudentBottomNav is hidden.
        "mx-auto flex w-full flex-1 flex-col gap-6 px-4 pt-6 pb-24 sm:px-6 sm:pt-8 lg:pb-10 animate-fade-slide-up",
        "focus:outline-none",
        WIDTH[width],
        className,
      )}
    >
      {children}
    </main>
  );
}
