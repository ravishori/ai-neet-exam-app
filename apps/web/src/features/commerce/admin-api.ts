import { apiClient } from "@/lib/api-client";

export type AdminOrder = {
  id: string;
  orderNumber: string | null;
  userId: string;
  amountPaise: number;
  currency: string;
  status: string;
  razorpayOrderId: string | null;
  razorpayPaymentId: string | null;
  createdAt: string | null;
  paidAt: string | null;
};

export type FoundingStatus = {
  maxPurchases: number | null;
  purchaseCount: number;
  remaining: number | null;
  isActive: boolean;
} | null;

export const adminCommerceApi = {
  listOrders: () => apiClient.get<AdminOrder[]>("/api/v1/admin/commerce/orders"),
  foundingStatus: () => apiClient.get<FoundingStatus>("/api/v1/admin/commerce/founding-status"),
};
