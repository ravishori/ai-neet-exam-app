import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const setTheme = vi.fn();

vi.mock("next-themes", () => ({
  useTheme: () => ({ theme: "system", setTheme }),
}));

import { ThemeToggle } from "@/components/ds/theme-toggle";

describe("Phase A9 ThemeToggle", () => {
  beforeEach(() => {
    setTheme.mockClear();
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("after mount exposes a labeled menu trigger without layout-breaking disabled state", async () => {
    render(<ThemeToggle />);

    await waitFor(() => {
      const trigger = screen.getByRole("button", { name: "Theme: System" });
      expect(trigger).toHaveAttribute("aria-haspopup", "menu");
      expect(trigger).toHaveAttribute("data-slot", "dropdown-menu-trigger");
      expect(trigger).not.toBeDisabled();
    });
  });

  it("lists Light, Dark, and System with the current theme marked", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Theme: System" })).not.toBeDisabled();
    });

    await user.click(screen.getByRole("button", { name: "Theme: System" }));
    const menu = await screen.findByRole("menu");

    expect(within(menu).getByRole("menuitem", { name: /Light/i })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: /Dark/i })).toBeInTheDocument();
    const system = within(menu).getByRole("menuitem", { name: /System/i });
    expect(system).toHaveAttribute("aria-current", "true");

    await user.click(within(menu).getByRole("menuitem", { name: /Dark/i }));
    expect(setTheme).toHaveBeenCalledWith("dark");
  });
});
