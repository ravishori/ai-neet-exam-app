"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { APP_THEME_STORAGE_KEY, isAppTheme, type AppTheme } from "@/lib/app-theme";

type AppThemeContextValue = {
  /** `undefined` = no visual theme selected (original palette). */
  appTheme: AppTheme | undefined;
  setAppTheme: (theme: AppTheme | undefined) => void;
};

const AppThemeContext = createContext<AppThemeContextValue | null>(null);

function readStoredAppTheme(): AppTheme | undefined {
  try {
    const stored = window.localStorage.getItem(APP_THEME_STORAGE_KEY);
    return isAppTheme(stored) ? stored : undefined;
  } catch {
    // Storage can throw (privacy mode, disabled cookies, etc.) — fall back
    // to the unthemed default rather than breaking the app.
    return undefined;
  }
}

function applyAppTheme(theme: AppTheme | undefined) {
  const root = document.documentElement;
  if (theme) {
    root.setAttribute("data-app-theme", theme);
  } else {
    root.removeAttribute("data-app-theme");
  }
}

/**
 * Independent visual-theme layer, deliberately not routed through
 * next-themes: next-themes keeps sole ownership of `class="dark"` /
 * light / system exactly as before. This provider only ever touches
 * `data-app-theme` on <html>, and both layers compose purely through the
 * shared semantic CSS tokens in globals.css.
 *
 * The initial DOM attribute is already set synchronously before hydration
 * by the inline script rendered via `<AppThemeScript />` in the root
 * layout (mirrors how next-themes itself avoids a flash of the wrong
 * theme) — this provider's first render just reads the same source of
 * truth into React state so `useAppTheme()` reflects it without causing a
 * second, visible attribute change.
 */
export function AppThemeProvider({ children }: { children: React.ReactNode }) {
  const [appTheme, setAppThemeState] = useState<AppTheme | undefined>(undefined);

  useEffect(() => {
    setAppThemeState(readStoredAppTheme());

    function onStorage(event: StorageEvent) {
      if (event.key !== null && event.key !== APP_THEME_STORAGE_KEY) return;
      const next = readStoredAppTheme();
      setAppThemeState(next);
      applyAppTheme(next);
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const setAppTheme = useCallback((theme: AppTheme | undefined) => {
    setAppThemeState(theme);
    applyAppTheme(theme);
    try {
      if (theme) {
        window.localStorage.setItem(APP_THEME_STORAGE_KEY, theme);
      } else {
        window.localStorage.removeItem(APP_THEME_STORAGE_KEY);
      }
    } catch {
      // Non-fatal: the theme still applies for this session even if it
      // can't persist.
    }
  }, []);

  const value = useMemo(() => ({ appTheme, setAppTheme }), [appTheme, setAppTheme]);

  return <AppThemeContext.Provider value={value}>{children}</AppThemeContext.Provider>;
}

export function useAppTheme(): AppThemeContextValue {
  const ctx = useContext(AppThemeContext);
  if (!ctx) {
    throw new Error("useAppTheme must be used within an AppThemeProvider");
  }
  return ctx;
}
