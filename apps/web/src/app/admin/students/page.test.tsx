import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";

const list = vi.fn();
const updateUser = vi.fn();
vi.mock("@/features/users/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/users/api")>("@/features/users/api");
  return {
    ...actual,
    usersApi: {
      list: (...args: unknown[]) => list(...args),
      updateUser: (...args: unknown[]) => updateUser(...args),
    },
  };
});

import AdminStudentsPage from "@/app/admin/students/page";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AdminStudentsPage />
    </QueryClientProvider>,
  );
}

const STUDENT = {
  id: "u1",
  email: "student@example.com",
  first_name: "Asha",
  last_name: "Rao",
  display_name: "Asha Rao",
  phone: null,
  mobile_e164: null,
  state_code: null,
  city_name: null,
  status: "active",
  email_verified: true,
  roles: ["STUDENT"],
  preferred_language: "en",
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("Admin Students page", () => {
  beforeEach(() => {
    list.mockReset();
    updateUser.mockReset();
    list.mockResolvedValue({ data: [STUDENT], meta: { total: 1, limit: 20, offset: 0 } });
  });

  it("renders the student list scoped to the STUDENT role", async () => {
    renderPage();
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
    await waitFor(() => expect(list).toHaveBeenCalledWith(expect.objectContaining({ role: "STUDENT" })));
  });

  it("shows a permission-denied message instead of the list when forbidden", async () => {
    list.mockRejectedValue(new ApiError("Forbidden", "PERMISSION_DENIED", 403));
    renderPage();
    expect(await screen.findByText(/don't have the/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no students", async () => {
    list.mockResolvedValue({ data: [], meta: { total: 0, limit: 20, offset: 0 } });
    renderPage();
    expect(await screen.findByText("No students found")).toBeInTheDocument();
  });

  it("toggles a student's status via the row action", async () => {
    updateUser.mockResolvedValue({ ...STUDENT, status: "suspended" });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Asha Rao");
    await user.click(screen.getByRole("button", { name: "Suspend" }));
    await waitFor(() => expect(updateUser).toHaveBeenCalledWith("u1", { status: "suspended" }));
  });

  it("re-queries with the search term", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Asha Rao");
    await user.type(screen.getByPlaceholderText("Search by email…"), "asha");
    await waitFor(() => expect(list).toHaveBeenCalledWith(expect.objectContaining({ search: "asha" })));
  });
});
