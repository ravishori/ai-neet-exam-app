"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/features/auth/api";
import { forgotPasswordSchema, type ForgotPasswordValues } from "@/features/auth/schemas";

export default function ForgotPasswordPage() {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordValues>({ resolver: zodResolver(forgotPasswordSchema) });
  const mutation = useMutation({ mutationFn: authApi.forgotPassword });

  return (
    <main className="flex flex-1 items-center justify-center px-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Forgot password</CardTitle>
          <CardDescription>We&apos;ll send a reset link if that email has an account.</CardDescription>
        </CardHeader>
        <CardContent>
          {mutation.isSuccess ? (
            <p className="text-sm text-muted-foreground">
              If that email exists, a reset link has been sent. In dev, check the backend console log.
            </p>
          ) : (
            <form
              onSubmit={handleSubmit((values) => mutation.mutate(values))}
              className="flex flex-col gap-4"
            >
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="email">Email</Label>
                <Input id="email" type="email" {...register("email")} />
                {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
              </div>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Sending…" : "Send reset link"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
