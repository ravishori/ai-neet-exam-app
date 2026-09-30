"use client";

import { Check, Moon, Sun, Monitor, Sparkles } from "lucide-react";
import { useTheme } from "next-themes";

import { useAppTheme } from "@/components/app-theme-provider";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMounted } from "@/hooks/use-mounted";
import { APP_THEMES, APP_THEME_LABELS } from "@/lib/app-theme";
import { cn } from "@/lib/utils";

const triggerClass =
  "inline-flex touch-target touch-manipulation size-9 shrink-0 items-center justify-center rounded-md border border-transparent text-muted-foreground outline-none transition-[color,background-color,border-color] duration-150 hover:border-border/60 hover:bg-muted/70 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:opacity-60 motion-reduce:transition-none data-popup-open:border-border/80 data-popup-open:bg-muted/80 data-popup-open:text-foreground";

const THEME_OPTIONS = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
] as const;

function themeAriaLabel(theme: string | undefined) {
  if (theme === "dark") return "Theme: Dark";
  if (theme === "light") return "Theme: Light";
  return "Theme: System";
}

/**
 * Theme control (Phase A9).
 * Base UI Menu is deferred until after mount to avoid SSR/client id hydration mismatches.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const { appTheme, setAppTheme } = useAppTheme();
  const mounted = useMounted();

  if (!mounted) {
    return (
      <button
        type="button"
        className={cn(triggerClass, className)}
        aria-label="Theme: System"
        disabled
      >
        <Monitor className="size-4" aria-hidden />
      </button>
    );
  }

  const resolved = theme ?? "system";
  const ActiveIcon =
    resolved === "dark" ? Moon : resolved === "light" ? Sun : Monitor;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(triggerClass, className)}
        aria-label={themeAriaLabel(resolved)}
        aria-haspopup="menu"
      >
        <ActiveIcon className="size-4" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-40 p-1.5" data-theme-menu>
        {THEME_OPTIONS.map(({ value, label, Icon }) => {
          const selected = resolved === value;
          return (
            <DropdownMenuItem
              key={value}
              className={cn(
                "min-h-9 cursor-pointer gap-2 rounded-md px-2 py-2",
                selected && "bg-primary/10 font-medium text-primary focus:bg-primary/12 focus:text-primary",
              )}
              aria-current={selected ? "true" : undefined}
              onClick={() => setTheme(value)}
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              <span className="flex-1">{label}</span>
              {selected ? <Check className="size-3.5 shrink-0 opacity-80" aria-hidden /> : null}
            </DropdownMenuItem>
          );
        })}
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Sparkles className="size-3.5" aria-hidden />
            Appearance
          </DropdownMenuLabel>
          <DropdownMenuItem
            className={cn(
              "min-h-9 cursor-pointer gap-2 rounded-md px-2 py-2",
              !appTheme && "bg-primary/10 font-medium text-primary focus:bg-primary/12 focus:text-primary",
            )}
            aria-current={!appTheme ? "true" : undefined}
            onClick={() => setAppTheme(undefined)}
          >
            <span className="size-4 shrink-0 rounded-full border border-border/70 bg-background" aria-hidden />
            <span className="flex-1">Default</span>
            {!appTheme ? <Check className="size-3.5 shrink-0 opacity-80" aria-hidden /> : null}
          </DropdownMenuItem>
          {APP_THEMES.map((value) => {
            const selected = appTheme === value;
            return (
              <DropdownMenuItem
                key={value}
                className={cn(
                  "min-h-9 cursor-pointer gap-2 rounded-md px-2 py-2",
                  selected && "bg-primary/10 font-medium text-primary focus:bg-primary/12 focus:text-primary",
                )}
                aria-current={selected ? "true" : undefined}
                onClick={() => setAppTheme(value)}
              >
                <span className={cn("size-4 shrink-0 rounded-full", appThemeSwatchClass[value])} aria-hidden />
                <span className="flex-1">{APP_THEME_LABELS[value]}</span>
                {selected ? <Check className="size-3.5 shrink-0 opacity-80" aria-hidden /> : null}
              </DropdownMenuItem>
            );
          })}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

const appThemeSwatchClass: Record<(typeof APP_THEMES)[number], string> = {
  cosmic: "bg-[linear-gradient(135deg,#6d28d9,#22d3ee)]",
  mint: "bg-[linear-gradient(135deg,#10b981,#5eead4)]",
  bloom: "bg-[linear-gradient(135deg,#ec4899,#fb923c)]",
  electric: "bg-[linear-gradient(135deg,#0f172a,#22d3ee)]",
  sunset: "bg-[linear-gradient(135deg,#f97316,#c026d3)]",
  arctic: "bg-[linear-gradient(135deg,#38bdf8,#6366f1)]",
};
