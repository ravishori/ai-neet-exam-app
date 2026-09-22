"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { adminCommerceApi } from "@/features/commerce/admin-api";
import { paiseToRupeeLabel } from "@/features/commerce/api";

/**
 * Administrative visibility screen only — payment verification stays fully
 * automatic and cryptographic (Razorpay signature, verified server-side).
 * There is no manual UTR/approval action here by design.
 */
export default function AdminCommercePage() {
  const { data: orders, isLoading: ordersLoading } = useQuery({
    queryKey: ["admin", "commerce", "orders"],
    queryFn: adminCommerceApi.listOrders,
  });
  const { data: founding, isLoading: foundingLoading } = useQuery({
    queryKey: ["admin", "commerce", "founding-status"],
    queryFn: adminCommerceApi.foundingStatus,
  });

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <div>
          <h1 className="font-heading text-xl font-semibold">Commerce</h1>
          <p className="text-sm text-muted-foreground">Orders, payments, and founding-offer allocation status.</p>
        </div>

        {foundingLoading ? (
          <Skeleton className="h-20 w-64" />
        ) : founding ? (
          <div className="flex w-fit flex-col gap-1 rounded-md border border-border px-4 py-3">
            <span className="text-sm font-medium">Founding offer (₹499)</span>
            <span className="text-sm text-muted-foreground">
              {founding.purchaseCount} of {founding.maxPurchases ?? "—"} allocated
              {founding.remaining !== null && ` — ${founding.remaining} remaining`}
            </span>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Founding plan not found.</p>
        )}

        {ordersLoading ? (
          <Skeleton className="h-96 w-full" aria-busy="true" aria-live="polite" />
        ) : !orders || orders.length === 0 ? (
          <EmptyState title="No orders yet" />
        ) : (
          <div className="overflow-x-auto rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Order</TableHead>
                  <TableHead>Student</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Razorpay Payment ID</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Paid</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.map((order) => (
                  <TableRow key={order.id}>
                    <TableCell className="font-mono text-xs">{order.orderNumber ?? order.id.slice(0, 8)}</TableCell>
                    <TableCell className="font-mono text-xs">{order.userId.slice(0, 8)}</TableCell>
                    <TableCell>{paiseToRupeeLabel(order.amountPaise)}</TableCell>
                    <TableCell>
                      <Badge variant={order.status === "PAID" ? "default" : "secondary"}>{order.status}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{order.razorpayPaymentId ?? "—"}</TableCell>
                    <TableCell className="text-xs">
                      {order.createdAt ? new Date(order.createdAt).toLocaleString("en-IN") : "—"}
                    </TableCell>
                    <TableCell className="text-xs">
                      {order.paidAt ? new Date(order.paidAt).toLocaleString("en-IN") : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </main>
  );
}
