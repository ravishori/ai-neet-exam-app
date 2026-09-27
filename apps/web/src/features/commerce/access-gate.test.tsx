import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const accessState = vi.fn();
vi.mock("@/features/commerce/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/commerce/api")>("@/features/commerce/api");
  return { ...actual, commerceApi: { ...actual.commerceApi, accessState: () => accessState() } };
});

import { AccessGate } from "@/features/commerce/access-gate";

function renderGate() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AccessGate>
        <div>Premium content</div>
      </AccessGate>
    </QueryClientProvider>,
  );
}

describe("AccessGate", () => {
  it("renders children when the backend reports active access", async () => {
    accessState.mockResolvedValue({ state: "TRIAL_ACTIVE", hasAccess: true, trialExpiresAt: null, entitlementExpiresAt: null });
    renderGate();
    expect(await screen.findByText("Premium content")).toBeInTheDocument();
  });

  it("renders the upgrade state instead of children when access is expired", async () => {
    accessState.mockResolvedValue({ state: "TRIAL_EXPIRED", hasAccess: false, trialExpiresAt: null, entitlementExpiresAt: null });
    renderGate();
    expect(await screen.findByText("Upgrade required")).toBeInTheDocument();
    expect(screen.queryByText("Premium content")).not.toBeInTheDocument();
  });

  it("cannot be overridden by any client-side state — it only ever renders what the backend response says", async () => {
    // No localStorage/query-string bypass exists in AccessGate's implementation
    // at all — this test documents that by setting a misleading localStorage
    // value and confirming it has zero effect on the rendered output.
    localStorage.setItem("hasAccess", "true");
    accessState.mockResolvedValue({ state: "NO_ACCESS", hasAccess: false, trialExpiresAt: null, entitlementExpiresAt: null });
    renderGate();
    expect(await screen.findByText("Upgrade required")).toBeInTheDocument();
    localStorage.clear();
  });
});
