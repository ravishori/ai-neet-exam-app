import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AppHeader } from "@/components/app-header";

vi.mock("next/navigation", () => ({
  usePathname: () => "/student/practice",
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/features/auth/use-auth", () => ({
  useMe: () => ({ data: { display_name: "Asha", email: "asha@example.com", roles: [] } }),
  useLogout: () => ({ mutate: vi.fn() }),
}));

vi.mock("@/hooks/use-mounted", () => ({
  useMounted: () => true,
}));

vi.mock("@/components/ds/theme-toggle", () => ({
  ThemeToggle: () => <button type="button" aria-label="Theme: System" />,
}));

const primary = [
  { href: "/student/dashboard", label: "Dashboard" },
  { href: "/student/practice", label: "Practice" },
  { href: "/student/subjects", label: "Subjects" },
  { href: "/student/analytics", label: "Progress" },
];

const moreSections = [
  {
    label: "Study tools",
    links: [
      { href: "/student/flashcards", label: "Flashcards" },
      { href: "/student/mock-tests", label: "Mock Tests" },
      { href: "/student/questions", label: "Questions" },
      { href: "/student/attempts", label: "Attempts" },
      { href: "/student/study-plan", label: "Study Plan" },
    ],
  },
  {
    label: "Account",
    links: [
      { href: "/student/profile", label: "Profile" },
      { href: "/student/settings", label: "Settings" },
    ],
  },
];

function renderHeader() {
  return render(
    <AppHeader
      brandHref="/student/dashboard"
      primaryLinks={primary}
      moreSections={moreSections}
      navLabel="Student desktop"
    />,
  );
}

describe("Phase A6 AppHeader", () => {
  it("renders brand and primary student destinations", () => {
    renderHeader();

    expect(screen.getByLabelText("Trinetra home")).toHaveAttribute(
      "href",
      "/student/dashboard",
    );
    expect(screen.getByText("Trinetra")).toBeInTheDocument();
    expect(screen.getByText("NEET Prep")).toBeInTheDocument();
    for (const link of primary) {
      expect(
        screen.getByRole("link", { name: link.label, hidden: true }),
      ).toHaveAttribute("href", link.href);
    }
    expect(
      screen.getByRole("link", { name: "Practice", hidden: true }),
    ).toHaveAttribute("aria-current", "page");
  });

  it("exposes More, account, and theme controls with accessible names", () => {
    renderHeader();
    expect(screen.getByLabelText("More navigation")).toBeInTheDocument();
    expect(screen.getByLabelText("Account menu")).toBeInTheDocument();
    expect(screen.getByLabelText("Theme: System")).toBeInTheDocument();
    expect(screen.getByLabelText("Open navigation menu")).toBeInTheDocument();
  });
});

describe("Phase A9 account menu", () => {
  it("shows initials avatar and opens Profile, Settings, Sign out", async () => {
    const user = userEvent.setup();
    renderHeader();

    expect(screen.getByLabelText("Account menu")).toHaveAttribute("data-account-menu-trigger");
    expect(screen.getByText("A")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Account menu"));
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: /Profile/i })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: /Settings/i })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: /Sign out/i })).toBeInTheDocument();
  });
});

describe("Phase A7 desktop navigation", () => {
  it("marks the active primary link with aria-current and data-nav-active", () => {
    renderHeader();
    const practice = screen.getByRole("link", { name: "Practice", hidden: true });
    expect(practice).toHaveAttribute("aria-current", "page");
    expect(practice).toHaveAttribute("data-nav-active", "true");
    expect(
      screen.getByRole("link", { name: "Dashboard", hidden: true }),
    ).not.toHaveAttribute("aria-current");
  });

  it("exposes a desktop nav cluster and More as a secondary control", () => {
    renderHeader();
    expect(document.querySelector("[data-desktop-nav]")).toBeTruthy();
    const more = screen.getByLabelText("More navigation");
    expect(more).toHaveAttribute("data-nav-more", "idle");
    expect(more).toHaveAttribute("aria-haspopup", "menu");
  });

  it("opens More with Study tools and Account groups (destinations unchanged)", async () => {
    const user = userEvent.setup();
    renderHeader();
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
