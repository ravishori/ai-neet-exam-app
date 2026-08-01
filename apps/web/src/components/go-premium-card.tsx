"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";
import { commerceApi } from "@/features/commerce/api";

declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void };
  }
}

const RAZORPAY_CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";

function loadRazorpayScript(): Promise<boolean> {
  if (window.Razorpay) return Promise.resolve(true);
  return new Promise((resolve) => {
    const script = document.createElement("script");
    script.src = RAZORPAY_CHECKOUT_SRC;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

export function GoPremiumCard() {
  const queryClient = useQueryClient();
  const { data: status } = useQuery({ queryKey: ["commerce", "status"], queryFn: commerceApi.status });

  const purchase = useMutation({
    mutationFn: async () => {
      const order = await commerceApi.createOrder();
      const scriptLoaded = await loadRazorpayScript();
      if (!scriptLoaded || !window.Razorpay) {
        throw new Error("Could not load the Razorpay checkout script.");
      }

      return new Promise<void>((resolve, reject) => {
        const razorpay = new window.Razorpay!({
          key: order.razorpay_key_id,
          amount: Math.round(order.amount_inr * 100),
          currency: "INR",
          name: "Trinetra AI Learning OS",
          description: "Premium access",
          order_id: order.razorpay_order_id,
          handler: async (response: { razorpay_payment_id: string; razorpay_signature: string }) => {
            try {
              await commerceApi.verifyOrder(order.id, {
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
              });
              resolve();
            } catch (err) {
              reject(err);
            }
          },
          modal: { ondismiss: () => reject(new Error("Payment cancelled")) },
        });
        razorpay.open();
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["commerce", "status"] }),
  });

  if (status?.is_premium) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Premium</CardTitle>
        </CardHeader>
        <CardContent>
          <Badge>Active</Badge>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Go Premium</CardTitle>
        <CardDescription>Unlimited mock tests and priority AI Tutor access — ₹499 one-time.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {purchase.isError && (
          <Alert variant="destructive">
            <AlertDescription>
              {purchase.error instanceof ApiError && purchase.error.code === "PAYMENT_GATEWAY_NOT_CONFIGURED"
                ? "Payment isn't configured yet in this environment — check back once it's live."
                : purchase.error instanceof ApiError
                  ? purchase.error.message
                  : "Something went wrong."}
            </AlertDescription>
          </Alert>
        )}
        <Button className="w-fit" disabled={purchase.isPending} onClick={() => purchase.mutate()}>
          {purchase.isPending ? "Processing…" : "Pay ₹499"}
        </Button>
      </CardContent>
    </Card>
  );
}
