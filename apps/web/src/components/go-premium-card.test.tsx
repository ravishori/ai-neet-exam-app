import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api-client";

const accessState = vi.fn();
const pricing = vi.fn();
const createOrder = vi.fn();
const verifyOrder = vi.fn();

vi.mock("@/features/commerce/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/commerce/api")>("@/features/commerce/api");
  return {
    ...actual,
    commerceApi: {
      accessState: () => accessState(),
      pricing: () => pricing(),
      createOrder: () => createOrder(),
      verifyOrder: (id: string, data: unknown) => verifyOrder(id, data),
    },
  };
});

import { GoPremiumCard } from "@/components/go-premium-card";

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <GoPremiumCard />
    </QueryClientProvider>,
  );
}

describe("GoPremiumCard", () => {
  it("renders the trial banner with days remaining for TRIAL_ACTIVE", async () => {
    accessState.mockResolvedValue({
      state: "TRIAL_ACTIVE",
      hasAccess: true,
      trialExpiresAt: new Date(Date.now() + 5 * 86400000).toISOString(),
      entitlementExpiresAt: null,
    });
    pricing.mockResolvedValue([
      { code: "FOUNDING_500", amountPaise: 49900, currency: "INR", durationDays: 365, maxPurchases: 500, remaining: 120 },
      { code: "STANDARD_ANNUAL", amountPaise: 99900, currency: "INR", durationDays: 365, maxPurchases: null, remaining: null },
    ]);

    renderCard();

    expect(await screen.findByText("15-Day Free Trial")).toBeInTheDocument();
    expect(await screen.findByText(/5 days remaining/)).toBeInTheDocument();
  });

  it("displays the backend-provided founding price, never a hardcoded one", async () => {
    accessState.mockResolvedValue({
      state: "TRIAL_EXPIRED",
      hasAccess: false,
      trialExpiresAt: new Date(Date.now() - 86400000).toISOString(),
      entitlementExpiresAt: null,
    });
    pricing.mockResolvedValue([
      { code: "FOUNDING_500", amountPaise: 49900, currency: "INR", durationDays: 365, maxPurchases: 500, remaining: 3 },
      { code: "STANDARD_ANNUAL", amountPaise: 99900, currency: "INR", durationDays: 365, maxPurchases: null, remaining: null },
    ]);

    renderCard();

    expect(await screen.findByText("Your free trial has ended")).toBeInTheDocument();
    expect(await screen.findByText("₹499")).toBeInTheDocument();
    expect(await screen.findByText(/Founding Student Offer/)).toBeInTheDocument();
  });

  it("shows the standard price once the founding offer is exhausted (backend-determined)", async () => {
    accessState.mockResolvedValue({
      state: "TRIAL_EXPIRED",
      hasAccess: false,
      trialExpiresAt: new Date(Date.now() - 86400000).toISOString(),
      entitlementExpiresAt: null,
    });
    pricing.mockResolvedValue([
      { code: "FOUNDING_500", amountPaise: 49900, currency: "INR", durationDays: 365, maxPurchases: 500, remaining: 0 },
      { code: "STANDARD_ANNUAL", amountPaise: 99900, currency: "INR", durationDays: 365, maxPurchases: null, remaining: null },
    ]);

    renderCard();

    expect(await screen.findByText("₹999")).toBeInTheDocument();
    expect(screen.queryByText(/Founding Student Offer/)).not.toBeInTheDocument();
  });

  it("shows active entitlement expiry for PAID_ACTIVE, never a false-premium message before backend confirmation", async () => {
    accessState.mockResolvedValue({
      state: "PAID_ACTIVE",
      hasAccess: true,
      trialExpiresAt: null,
      entitlementExpiresAt: "2027-06-30T00:00:00Z",
    });
    pricing.mockResolvedValue([]);

    renderCard();

    expect(await screen.findByText("All Access")).toBeInTheDocument();
    expect(await screen.findByText(/Premium access active until/)).toBeInTheDocument();
  });

  it("does not grant access on a failed backend verification — access-state stays unchanged", async () => {
    accessState.mockResolvedValue({
      state: "TRIAL_EXPIRED",
      hasAccess: false,
      trialExpiresAt: new Date(Date.now() - 86400000).toISOString(),
      entitlementExpiresAt: null,
    });
    pricing.mockResolvedValue([
      { code: "FOUNDING_500", amountPaise: 49900, currency: "INR", durationDays: 365, maxPurchases: 500, remaining: 10 },
    ]);
    createOrder.mockRejectedValue(new ApiError("Order failed", "PAYMENT_GATEWAY_NOT_CONFIGURED", 503));

    renderCard();

    const button = await screen.findByRole("button", { name: /Pay/ });
    button.click();

    await waitFor(() => {
      expect(screen.getAllByText(/Network error|isn't configured/).length).toBeGreaterThan(0);
    });
    // Still shows the pre-purchase trial-expired state — no premium badge appeared.
    expect(screen.queryByText("All Access")).not.toBeInTheDocument();
  });
});
