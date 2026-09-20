import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Canonical field select (Phase A5).
 * Native &lt;select&gt; preserves form semantics, keyboard, and value/onChange.
 * Styled to match Input / design tokens. Prefer this over ad-hoc className selects.
 * Base UI Select deferred — native control avoids menu ID hydration risk.
 */
function FieldSelect({ className, children, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      data-slot="field-select"
      className={cn(
        "h-9 w-full min-w-0 rounded-lg border border-input bg-background px-2.5 text-sm text-foreground outline-none transition-colors",
        "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-input/50",
        "dark:bg-input/30 dark:disabled:bg-input/80",
        "aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export { FieldSelect };
