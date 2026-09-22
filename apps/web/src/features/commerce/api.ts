import { apiClient } from "@/lib/api-client";

// AccessState mirrors AccessService.get_access_state exactly — the frontend
// never computes access itself, only displays what the backend returns.
export type AccessStateCode = "TRIAL_ACTIVE" | "TRIAL_EXPIRING" | "TRIAL_EXPIRED" | "PAID_ACTIVE" | "NO_ACCESS";

export type AccessState = {
  state: AccessStateCode;
  hasAccess: boolean;
  trialExpiresAt: string | null;
  entitlementExpiresAt: string | null;
};

export type PricingPlan = {
  code: "FOUNDING_500" | "STANDARD_ANNUAL" | string;
  amountPaise: number;
  currency: string;
  durationDays: number;
  maxPurchases: number | null;
  remaining: number | null;
};

export type CommerceOrder = {
  id: string;
  orderNumber: string | null;
  amountPaise: number;
  currency: string;
  status: "CREATED" | "PAYMENT_PENDING" | "PAID" | "FAILED" | "CANCELLED" | "EXPIRED" | "REFUNDED";
  razorpayOrderId: string | null;
  razorpayKeyId?: string;
};

export const commerceApi = {
  accessState: () => apiClient.get<AccessState>("/api/v1/commerce/access-state"),
  pricing: () => apiClient.get<PricingPlan[]>("/api/v1/commerce/pricing"),
  createOrder: () => apiClient.post<CommerceOrder>("/api/v1/commerce/orders"),
  verifyOrder: (orderId: string, data: { razorpay_payment_id: string; razorpay_signature: string }) =>
    apiClient.post<CommerceOrder>(`/api/v1/commerce/orders/${orderId}/verify`, data),
};

export function paiseToRupeeLabel(paise: number): string {
  return `₹${Math.round(paise / 100)}`;
}
