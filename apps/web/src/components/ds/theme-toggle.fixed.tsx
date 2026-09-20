"use client";

import { Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const triggerClass = cn(
    "flex size-8 items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50",
    className,
  );

  // Defer Base UI Menu until after mount to avoid SSR/client id mismatches
  // that Next.js surfaces as cryptic "[object Event]" / hydration overlays.
  if (!mounted) {
    return (
      <button type="button" className={triggerClass} aria-label="Toggle theme" disabled>
        <Monitor className="size-4" aria-hidden />
      </button>
    );
  }

  const icon =
    theme === "dark" ? (
      <Moon className="size-4" aria-hidden />
    ) : theme === "light" ? (
      <Sun className="size-4" aria-hidden />
    ) : (
      <Monitor className="size-4" aria-hidden />
    );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className={triggerClass} aria-label="Toggle theme">
        {icon}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-36">
        <DropdownMenuItem onClick={() => setTheme("light")}>
          <Sun className="size-4" aria-hidden />
          Light
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("dark")}>
          <Moon className="size-4" aria-hidden />
          Dark
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("system")}>
          <Monitor className="size-4" aria-hidden />
          System
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
