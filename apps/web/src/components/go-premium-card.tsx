"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";
import { commerceApi, paiseToRupeeLabel, type CommerceOrder } from "@/features/commerce/api";

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

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function daysRemaining(iso: string): number {
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

// Payment UX states — distinct from the server AccessState, this is purely
// client-side flow tracking for the checkout widget itself. Access is only
// ever considered active based on the server's access-state response
// (refetched after verification), never derived from any of these states.
type PaymentPhase =
  | "idle"
  | "creating_order"
  | "checkout_open"
  | "awaiting_verification"
  | "verification_failed"
  | "cancelled"
  | "network_error";

export function GoPremiumCard() {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<PaymentPhase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: access, isLoading: accessLoading } = useQuery({
    queryKey: ["commerce", "access-state"],
    queryFn: commerceApi.accessState,
  });
  const { data: plans } = useQuery({ queryKey: ["commerce", "pricing"], queryFn: commerceApi.pricing });

  const founding = plans?.find((p) => p.code === "FOUNDING_500");
  const standard = plans?.find((p) => p.code === "STANDARD_ANNUAL");
  // Backend is authoritative on whether the founding offer is still open —
  // the frontend never decides this itself.
  const foundingAvailable = founding && founding.remaining !== null && founding.remaining > 0;
  const applicablePlan = foundingAvailable ? founding : standard;

  const purchase = useMutation({
    mutationFn: async () => {
      setErrorMessage(null);
      setPhase("creating_order");
      let order: CommerceOrder;
      try {
        order = await commerceApi.createOrder();
      } catch (err) {
        setPhase("network_error");
        throw err;
      }

      const scriptLoaded = await loadRazorpayScript();
      if (!scriptLoaded || !window.Razorpay) {
        setPhase("network_error");
        throw new Error("Could not load the Razorpay checkout script.");
      }

      setPhase("checkout_open");
      return new Promise<void>((resolve, reject) => {
        const razorpay = new window.Razorpay!({
          key: order.razorpayKeyId,
          amount: order.amountPaise,
          currency: order.currency,
          name: "Trinetra AI Learning OS",
          description: "NEET All Access — Annual",
          order_id: order.razorpayOrderId,
          handler: async (response: { razorpay_payment_id: string; razorpay_signature: string }) => {
            // Razorpay's own success callback is NOT trusted as access
            // confirmation — it only tells us to now ask the backend to
            // perform the authoritative signature verification.
            setPhase("awaiting_verification");
            try {
              await commerceApi.verifyOrder(order.id, {
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
              });
              resolve();
            } catch (err) {
              setPhase("verification_failed");
              setErrorMessage(err instanceof ApiError ? err.message : "Payment verification failed.");
              reject(err);
            }
          },
          modal: {
            ondismiss: () => {
              setPhase("cancelled");
              reject(new Error("Payment cancelled"));
            },
          },
        });
        razorpay.open();
      });
    },
    onSuccess: async () => {
      // Access only becomes active once this refetch reflects the backend's
      // post-verification entitlement — never assumed eagerly.
      await queryClient.invalidateQueries({ queryKey: ["commerce", "access-state"] });
      setPhase("idle");
    },
  });

  if (accessLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-4 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!access) return null;

  if (access.state === "PAID_ACTIVE" && access.entitlementExpiresAt) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">All Access</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center gap-2">
          <Badge>Active</Badge>
          <span className="text-sm text-muted-foreground">
            Premium access active until {formatDate(access.entitlementExpiresAt)}.
          </span>
        </CardContent>
      </Card>
    );
  }

  const isTrialActive = access.state === "TRIAL_ACTIVE" || access.state === "TRIAL_EXPIRING";
  const trialDays = access.trialExpiresAt ? daysRemaining(access.trialExpiresAt) : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {isTrialActive ? "15-Day Free Trial" : "Your free trial has ended"}
        </CardTitle>
        <CardDescription>
          {isTrialActive
            ? trialDays !== null && `${trialDays} day${trialDays === 1 ? "" : "s"} remaining — your free trial is active.`
            : "Choose an annual plan to continue."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {applicablePlan ? (
          <div className="flex flex-col gap-1">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold">{paiseToRupeeLabel(applicablePlan.amountPaise)}</span>
              <span className="text-sm text-muted-foreground">/year</span>
            </div>
            {foundingAvailable ? (
              <Badge variant="secondary" className="w-fit">
                Founding Student Offer — first 500 students only
              </Badge>
            ) : (
              <span className="text-xs text-muted-foreground">Standard annual price</span>
            )}
          </div>
        ) : (
          <Skeleton className="h-6 w-32" />
        )}

        {phase === "network_error" && (
          <Alert variant="destructive">
            <AlertDescription>Network error — please check your connection and try again.</AlertDescription>
          </Alert>
        )}
        {phase === "cancelled" && (
          <Alert>
            <AlertDescription>Payment cancelled. No charge was made.</AlertDescription>
          </Alert>
        )}
        {phase === "verification_failed" && (
          <Alert variant="destructive">
            <AlertDescription>
              {errorMessage ?? "We couldn't verify that payment. If money was deducted, contact support before retrying."}
            </AlertDescription>
          </Alert>
        )}
        {phase === "awaiting_verification" && (
          <Alert>
            <AlertDescription>Payment submitted — awaiting verification. Please don&apos;t close this page.</AlertDescription>
          </Alert>
        )}
        {purchase.isError && phase === "network_error" && purchase.error instanceof ApiError && (
          <p className="text-xs text-muted-foreground">
            {purchase.error.code === "PAYMENT_GATEWAY_NOT_CONFIGURED"
              ? "Payment isn't configured yet in this environment — check back once it's live."
              : purchase.error.message}
          </p>
        )}

        <Button
          className="w-fit"
          disabled={purchase.isPending || !applicablePlan}
          onClick={() => purchase.mutate()}
        >
          {phase === "creating_order"
            ? "Creating order…"
            : phase === "checkout_open"
              ? "Waiting for payment…"
              : phase === "awaiting_verification"
                ? "Verifying…"
                : applicablePlan
                  ? `Pay ${paiseToRupeeLabel(applicablePlan.amountPaise)}`
                  : "Loading plan…"}
        </Button>
      </CardContent>
    </Card>
  );
}
