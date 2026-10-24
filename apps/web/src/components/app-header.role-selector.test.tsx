import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AppHeader } from "@/components/app-header";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin",
  useRouter: () => ({ push: vi.fn() }),
}));

const switchRoleMutate = vi.fn();

vi.mock("@/features/auth/use-auth", () => ({
  useMe: () => ({
    data: {
      display_name: "Ravi",
      email: "ravi@example.com",
      roles: ["SUPER_ADMIN", "TEACHER", "CONTENT_MANAGER"],
      active_role: "SUPER_ADMIN",
      available_roles: ["SUPER_ADMIN", "TEACHER", "CONTENT_MANAGER"],
    },
  }),
  useLogout: () => ({ mutate: vi.fn() }),
  useSwitchRole: () => ({ mutate: switchRoleMutate }),
}));

vi.mock("@/hooks/use-mounted", () => ({
  useMounted: () => true,
}));

vi.mock("@/components/ds/theme-toggle", () => ({
  ThemeToggle: () => <button type="button" aria-label="Theme: System" />,
}));

function renderHeader() {
  return render(
    <AppHeader brandHref="/admin" primaryLinks={[{ href: "/admin", label: "Dashboard" }]} navLabel="Admin" />,
  );
}

describe("Prompt B account menu role selector", () => {
  it("shows the active role as a badge next to the account name", () => {
    renderHeader();
    expect(screen.getByText("Super Admin")).toBeInTheDocument();
  });

  it("lists every available role in the account menu with the active one selected, and a privilege-safety note", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByLabelText("Account menu"));

    const menu = await screen.findByRole("menu");
    const superAdminItem = within(menu).getByRole("menuitemradio", { name: "Super Admin" });
    const teacherItem = within(menu).getByRole("menuitemradio", { name: "Teacher" });
    const contentManagerItem = within(menu).getByRole("menuitemradio", { name: "Content Manager" });
    expect(superAdminItem).toHaveAttribute("aria-checked", "true");
    expect(teacherItem).toHaveAttribute("aria-checked", "false");
    expect(contentManagerItem).toHaveAttribute("aria-checked", "false");

    expect(
      within(menu).getByText(/switching never reduces what your account is actually allowed to do/i),
    ).toBeInTheDocument();
  });

  it("calls switchRole with the chosen role when a different one is selected", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByLabelText("Account menu"));
    const menu = await screen.findByRole("menu");

    await user.click(within(menu).getByRole("menuitemradio", { name: "Teacher" }));
    expect(switchRoleMutate).toHaveBeenCalledWith({ role: "TEACHER" });
  });
});
