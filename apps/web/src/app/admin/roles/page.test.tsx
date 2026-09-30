import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";

const list = vi.fn();
const listPermissions = vi.fn();
const updatePermissions = vi.fn();
vi.mock("@/features/roles/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/roles/api")>("@/features/roles/api");
  return {
    ...actual,
    rolesApi: {
      list: (...args: unknown[]) => list(...args),
      listPermissions: (...args: unknown[]) => listPermissions(...args),
      updatePermissions: (...args: unknown[]) => updatePermissions(...args),
    },
  };
});

import AdminRolesPage from "@/app/admin/roles/page";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminRolesPage />
    </QueryClientProvider>,
  );
}

const SUPER_ADMIN_ROLE = {
  id: "r1",
  code: "SUPER_ADMIN",
  name: "Super Admin",
  description: "Full access",
  permission_codes: ["users.manage", "audit.view"],
};

const ADMIN_ROLE = {
  id: "r2",
  code: "ADMIN",
  name: "Admin",
  description: "Standard admin",
  permission_codes: ["users.manage", "reports.view"],
};

describe("Admin Roles page", () => {
  beforeEach(() => {
    list.mockReset();
    listPermissions.mockReset();
    updatePermissions.mockReset();
    list.mockResolvedValue([SUPER_ADMIN_ROLE, ADMIN_ROLE]);
    listPermissions.mockResolvedValue([{ code: "users.manage" }, { code: "audit.view" }, { code: "content.edit" }]);
  });

  it("renders roles and marks SUPER_ADMIN as immutable", async () => {
    renderPage();
    expect(await screen.findByText("Super Admin")).toBeInTheDocument();
    expect(screen.getByText(/bypasses permission checks entirely/i)).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("shows a permission-denied message when the actor lacks users.manage", async () => {
    list.mockRejectedValue(new ApiError("Forbidden", "PERMISSION_DENIED", 403));
    renderPage();
    expect(await screen.findByText(/don't have the/i)).toBeInTheDocument();
  });

  it("shows the Capability View by default with grouped, human-readable labels", async () => {
    renderPage();
    await screen.findByText("Admin");
    expect(screen.getByText("Manage user accounts and roles")).toBeInTheDocument();
    expect(screen.getByText("View student/performance reports")).toBeInTheDocument();
    expect(screen.getByText("not yet enforced")).toBeInTheDocument();
    // technical checkboxes are hidden until expanded
    expect(screen.queryByRole("checkbox", { name: "content.edit" })).not.toBeInTheDocument();
  });

  it("expands Technical Permissions and saves updated permissions for a non-immutable role", async () => {
    updatePermissions.mockResolvedValue(ADMIN_ROLE);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Admin");
    await user.click(screen.getByRole("button", { name: "Show technical permissions" }));
    await user.click(screen.getByRole("checkbox", { name: "content.edit" }));
    await user.click(screen.getByRole("button", { name: "Save permissions" }));
    await waitFor(() =>
      expect(updatePermissions).toHaveBeenCalledWith(
        "r2",
        expect.arrayContaining(["users.manage", "reports.view", "content.edit"]),
      ),
    );
  });
});
