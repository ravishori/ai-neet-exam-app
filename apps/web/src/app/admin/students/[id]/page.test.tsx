import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "u1" }),
}));

const get = vi.fn();
const updateUser = vi.fn();
vi.mock("@/features/users/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/users/api")>("@/features/users/api");
  return {
    ...actual,
    usersApi: {
      get: (...args: unknown[]) => get(...args),
      updateUser: (...args: unknown[]) => updateUser(...args),
    },
  };
});

import StudentDetailPage from "@/app/admin/students/[id]/page";

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <StudentDetailPage />
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
  state_code: "KA",
  city_name: "Bengaluru",
  status: "active",
  email_verified: true,
  roles: ["STUDENT"],
  preferred_language: "en",
  last_login_at: null,
  created_at: "2026-01-01T00:00:00Z",
};

describe("Admin Student detail page", () => {
  beforeEach(() => {
    get.mockReset();
    updateUser.mockReset();
  });

  it("renders student details on success", async () => {
    get.mockResolvedValue(STUDENT);
    renderPage();
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText("Bengaluru")).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("u1");
  });

  it("shows an empty state on 404 without retrying", async () => {
    get.mockRejectedValue(new ApiError("Not found", "NOT_FOUND", 404));
    renderPage();
    expect(await screen.findByText("Student not found")).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("shows a permission-denied message when forbidden", async () => {
    get.mockRejectedValue(new ApiError("Forbidden", "PERMISSION_DENIED", 403));
    renderPage();
    expect(await screen.findByText(/don't have the/i, {}, { timeout: 10000 })).toBeInTheDocument();
  });

  it("toggles status via the detail page action", async () => {
    get.mockResolvedValue(STUDENT);
    updateUser.mockResolvedValue({ ...STUDENT, status: "suspended" });
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("Asha Rao");
    await user.click(screen.getByRole("button", { name: "Suspend account" }));
    await waitFor(() => expect(updateUser).toHaveBeenCalledWith("u1", { status: "suspended" }));
  });
});
