"use client";

import { Suspense, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { authApi } from "@/features/auth/api";

function VerifyEmailStatus() {
  const token = useSearchParams().get("token") ?? "";
  const mutation = useMutation({ mutationFn: authApi.verifyEmail });

  useEffect(() => {
    if (token) mutation.mutate({ token });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (!token) return <p className="text-sm text-muted-foreground">Missing verification token.</p>;
  if (mutation.isPending) return <p className="text-sm text-muted-foreground">Verifying…</p>;
  if (mutation.isError) return <p className="text-sm text-destructive">That link is invalid or expired.</p>;
  if (mutation.isSuccess) return <p className="text-sm">Email verified — you can close this tab.</p>;
  return null;
}

export default function VerifyEmailPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Verify email</CardTitle>
          <CardDescription>Confirming your email address.</CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense>
            <VerifyEmailStatus />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  );
}
