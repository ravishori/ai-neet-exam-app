import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  MOBILE_MORE_LINKS,
  MOBILE_MORE_SECTIONS,
  StudentBottomNav,
} from "@/components/ds/student-bottom-nav";

vi.mock("next/navigation", () => ({
  usePathname: () => "/student/practice",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/hooks/use-mounted", () => ({
  useMounted: () => true,
}));

describe("Phase A8 StudentBottomNav", () => {
  it("exposes Home→Dashboard plus Practice, Subjects, Progress destinations", () => {
    render(<StudentBottomNav />);
    const nav = screen.getByRole("navigation", { name: "Student mobile" });
    expect(nav).toHaveAttribute("data-mobile-nav");

    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute(
      "href",
      "/student/dashboard",
    );
    expect(screen.getByRole("link", { name: "Practice" })).toHaveAttribute(
      "href",
      "/student/practice",
    );
    expect(screen.getByRole("link", { name: "Subjects" })).toHaveAttribute(
      "href",
      "/student/subjects",
    );
    expect(screen.getByRole("link", { name: "Progress" })).toHaveAttribute(
      "href",
      "/student/analytics",
    );
  });

  it("marks the active primary destination with aria-current", () => {
    render(<StudentBottomNav />);
    const practice = screen.getByRole("link", { name: "Practice" });
    expect(practice).toHaveAttribute("aria-current", "page");
    expect(practice).toHaveAttribute("data-nav-active", "true");
    expect(screen.getByRole("link", { name: "Home" })).not.toHaveAttribute("aria-current");
  });

  it("opens More with Study tools and Account groups (routes unchanged)", async () => {
    const user = userEvent.setup();
    render(<StudentBottomNav />);
    await user.click(screen.getByLabelText("More navigation"));

    const menu = await screen.findByRole("menu");
    expect(within(menu).getByText("Study tools")).toBeInTheDocument();
    expect(within(menu).getByText("Account")).toBeInTheDocument();

    for (const label of [
      "Flashcards",
      "Mock Tests",
      "Questions",
      "Attempts",
      "Study Plan",
      "Profile",
      "Settings",
    ]) {
      expect(within(menu).getByRole("menuitem", { name: label })).toBeInTheDocument();
    }
  });
});

describe("Phase A8 mobile More IA", () => {
  it("preserves flat destination order for shell contracts", () => {
    expect(MOBILE_MORE_LINKS.map((l) => l.href)).toEqual([
      "/student/flashcards",
      "/student/mock-tests",
      "/student/questions",
      "/student/attempts",
      "/student/study-plan",
      "/student/profile",
      "/student/settings",
    ]);
    expect(MOBILE_MORE_SECTIONS.map((s) => s.label)).toEqual(["Study tools", "Account"]);
  });
});
