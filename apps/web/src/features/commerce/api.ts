import { apiClient } from "@/lib/api-client";

export type CommerceOrder = {
  id: string;
  amount_inr: number;
  status: "CREATED" | "PAID" | "FAILED";
  razorpay_order_id: string | null;
  razorpay_key_id: string;
};

export type CommerceStatus = { is_premium: boolean };

export const commerceApi = {
  status: () => apiClient.get<CommerceStatus>("/api/v1/commerce/status"),
  createOrder: () => apiClient.post<CommerceOrder>("/api/v1/commerce/orders"),
  verifyOrder: (orderId: string, data: { razorpay_payment_id: string; razorpay_signature: string }) =>
    apiClient.post<CommerceOrder>(`/api/v1/commerce/orders/${orderId}/verify`, data),
};
