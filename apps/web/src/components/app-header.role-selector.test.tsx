import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AppHeader } from "@/components/app-header";
import { ApiError } from "@/lib/api-client";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin",
  useRouter: () => ({ push: vi.fn() }),
}));

const switchRoleMutate = vi.fn();

let meData: Record<string, unknown> = {
  display_name: "Ravi",
  email: "ravi@example.com",
  roles: ["SUPER_ADMIN", "TEACHER", "CONTENT_MANAGER"],
  active_role: "SUPER_ADMIN",
  available_roles: ["SUPER_ADMIN", "TEACHER", "CONTENT_MANAGER"],
};

let switchRoleState: { mutate: typeof switchRoleMutate; isPending: boolean; isError: boolean; error: unknown } = {
  mutate: switchRoleMutate,
  isPending: false,
  isError: false,
  error: null,
};

vi.mock("@/features/auth/use-auth", () => ({
  useMe: () => ({ data: meData }),
  useLogout: () => ({ mutate: vi.fn() }),
  useSwitchRole: () => switchRoleState,
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

beforeEach(() => {
  switchRoleMutate.mockClear();
  meData = {
    display_name: "Ravi",
    email: "ravi@example.com",
    roles: ["SUPER_ADMIN", "TEACHER", "CONTENT_MANAGER"],
    active_role: "SUPER_ADMIN",
    available_roles: ["SUPER_ADMIN", "TEACHER", "CONTENT_MANAGER"],
  };
  switchRoleState = { mutate: switchRoleMutate, isPending: false, isError: false, error: null };
});

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
      within(menu).getByText(/switching never grants or reduces what your account is actually allowed to do/i),
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

  it("warns specifically that a SUPER_ADMIN account stays fully privileged regardless of the shown role", async () => {
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByLabelText("Account menu"));
    const menu = await screen.findByRole("menu");

    expect(
      within(menu).getByText(/a super_admin account stays fully privileged no matter which role is shown here/i),
    ).toBeInTheDocument();
  });

  it("omits the SUPER_ADMIN-specific warning for an account that doesn't hold that role", async () => {
    meData = {
      display_name: "Priya",
      email: "priya@example.com",
      roles: ["TEACHER", "CONTENT_MANAGER"],
      active_role: "CONTENT_MANAGER",
      available_roles: ["TEACHER", "CONTENT_MANAGER"],
    };
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByLabelText("Account menu"));
    const menu = await screen.findByRole("menu");

    expect(within(menu).queryByText(/super_admin/i)).not.toBeInTheDocument();
    // The general display-only note must still be present for any multi-role account.
    expect(within(menu).getByText(/display only/i)).toBeInTheDocument();
  });

  it("disables role options and shows a switching indicator while the mutation is pending", async () => {
    switchRoleState = { mutate: switchRoleMutate, isPending: true, isError: false, error: null };
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByLabelText("Account menu"));
    const menu = await screen.findByRole("menu");

    expect(within(menu).getByText(/switching…/i)).toBeInTheDocument();
    const teacherItem = within(menu).getByRole("menuitemradio", { name: "Teacher" });
    expect(teacherItem).toHaveAttribute("aria-disabled", "true");

    // Clicking a disabled item must not fire another switch while one is in flight.
    await user.click(teacherItem);
    expect(switchRoleMutate).not.toHaveBeenCalled();
  });

  it("shows the API's own error message inline when switching fails", async () => {
    switchRoleState = {
      mutate: switchRoleMutate,
      isPending: false,
      isError: true,
      error: new ApiError("You do not hold that role", "ROLE_NOT_ASSIGNED", 403),
    };
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByLabelText("Account menu"));
    const menu = await screen.findByRole("menu");

    expect(within(menu).getByRole("alert")).toHaveTextContent("You do not hold that role");
  });

  it("falls back to a generic message when the error isn't an ApiError", async () => {
    switchRoleState = {
      mutate: switchRoleMutate,
      isPending: false,
      isError: true,
      error: new Error("network exploded"),
    };
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByLabelText("Account menu"));
    const menu = await screen.findByRole("menu");

    expect(within(menu).getByRole("alert")).toHaveTextContent(/couldn't switch roles/i);
  });

  it("renders no role selector at all for a single-role account", async () => {
    meData = {
      display_name: "Student",
      email: "student@example.com",
      roles: ["STUDENT"],
      active_role: "STUDENT",
      available_roles: ["STUDENT"],
    };
    const user = userEvent.setup();
    renderHeader();
    await user.click(screen.getByLabelText("Account menu"));
    const menu = await screen.findByRole("menu");

    expect(within(menu).queryByText(/acting as/i)).not.toBeInTheDocument();
    expect(within(menu).queryAllByRole("menuitemradio")).toHaveLength(0);
  });
});
