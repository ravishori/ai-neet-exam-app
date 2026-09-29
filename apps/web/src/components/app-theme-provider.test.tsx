import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AppThemeProvider, useAppTheme } from "@/components/app-theme-provider";
import { APP_THEME_STORAGE_KEY } from "@/lib/app-theme";

function Probe() {
  const { appTheme, setAppTheme } = useAppTheme();
  return (
    <div>
      <span data-testid="app-theme">{appTheme ?? "default"}</span>
      <button type="button" onClick={() => setAppTheme("cosmic")}>
        cosmic
      </button>
      <button type="button" onClick={() => setAppTheme("bloom")}>
        bloom
      </button>
      <button type="button" onClick={() => setAppTheme(undefined)}>
        default
      </button>
    </div>
  );
}

describe("visual-theme layer (AppThemeProvider)", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-app-theme");
  });

  afterEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-app-theme");
  });

  it("defaults to no data-app-theme attribute (unthemed palette)", () => {
    render(
      <AppThemeProvider>
        <Probe />
      </AppThemeProvider>,
    );
    expect(document.documentElement.hasAttribute("data-app-theme")).toBe(false);
    expect(screen.getByTestId("app-theme")).toHaveTextContent("default");
  });

  it("picks up a previously-stored theme on mount", async () => {
    window.localStorage.setItem(APP_THEME_STORAGE_KEY, "mint");
    render(
      <AppThemeProvider>
        <Probe />
      </AppThemeProvider>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("app-theme")).toHaveTextContent("mint");
    });
  });

  it("ignores a corrupted/invalid stored value and falls back to default", () => {
    window.localStorage.setItem(APP_THEME_STORAGE_KEY, "not-a-real-theme");
    render(
      <AppThemeProvider>
        <Probe />
      </AppThemeProvider>,
    );
    expect(screen.getByTestId("app-theme")).toHaveTextContent("default");
  });

  it("applies data-app-theme on <html> and persists to localStorage immediately, without reload", async () => {
    const user = userEvent.setup();
    render(
      <AppThemeProvider>
        <Probe />
      </AppThemeProvider>,
    );

    await user.click(screen.getByRole("button", { name: "cosmic" }));

    expect(document.documentElement.getAttribute("data-app-theme")).toBe("cosmic");
    expect(window.localStorage.getItem(APP_THEME_STORAGE_KEY)).toBe("cosmic");
    expect(screen.getByTestId("app-theme")).toHaveTextContent("cosmic");

    await user.click(screen.getByRole("button", { name: "bloom" }));
    expect(document.documentElement.getAttribute("data-app-theme")).toBe("bloom");
    expect(window.localStorage.getItem(APP_THEME_STORAGE_KEY)).toBe("bloom");

    await user.click(screen.getByRole("button", { name: "default" }));
    expect(document.documentElement.hasAttribute("data-app-theme")).toBe(false);
    expect(window.localStorage.getItem(APP_THEME_STORAGE_KEY)).toBeNull();
  });

  it("does not touch next-themes' class attribute on <html>", async () => {
    document.documentElement.classList.add("dark");
    const user = userEvent.setup();
    render(
      <AppThemeProvider>
        <Probe />
      </AppThemeProvider>,
    );

    await user.click(screen.getByRole("button", { name: "cosmic" }));

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    document.documentElement.classList.remove("dark");
  });
});
