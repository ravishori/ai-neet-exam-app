import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { AppHeader } from "@/components/app-header";

vi.mock("next/navigation", () => ({
  usePathname: () => "/student/dashboard",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/features/auth/use-auth", () => ({
  useMe: () => ({ data: undefined }),
  useLogout: () => ({ mutate: vi.fn() }),
}));

vi.mock("@/hooks/use-mounted", () => ({
  useMounted: () => false,
}));

vi.mock("@/components/ds/theme-toggle", () => ({
  ThemeToggle: () => (
    <button type="button" aria-label="Theme: System" disabled />
  ),
}));

describe("FRONTEND-A12 AppHeader mount deferral", () => {
  it("does not emit Base UI menu triggers before mount", () => {
    const { container } = render(
      <AppHeader
        brandHref="/student/dashboard"
        primaryLinks={[
          { href: "/student/dashboard", label: "Dashboard" },
          { href: "/student/practice", label: "Practice" },
        ]}
        moreSections={[
          {
            label: "Study tools",
            links: [{ href: "/student/flashcards", label: "Flashcards" }],
          },
        ]}
        navLabel="Student desktop"
      />,
    );

    expect(container.querySelectorAll("[id^='base-ui-']")).toHaveLength(0);
    expect(container.querySelectorAll("[data-slot='dropdown-menu-trigger']")).toHaveLength(
      0,
    );
    expect(screen.getByLabelText("Account menu")).toBeDisabled();
    expect(screen.getByLabelText("Open navigation menu")).toBeDisabled();
    expect(screen.getByLabelText("More navigation")).toBeDisabled();
  });
});
