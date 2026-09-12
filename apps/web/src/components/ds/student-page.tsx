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

/** Shared student main shell: atmosphere-friendly padding, bottom-nav clearance, fade-in. */
export function StudentPage({ children, className, width = "xl" }: StudentPageProps) {
  return (
    <main
      className={cn(
        "mx-auto flex w-full flex-1 flex-col gap-6 px-4 py-6 pb-24 sm:px-6 sm:py-8 lg:pb-10 animate-fade-slide-up",
        WIDTH[width],
        className,
      )}
    >
      {children}
    </main>
  );
}
