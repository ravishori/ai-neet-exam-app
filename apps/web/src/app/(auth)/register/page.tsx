"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useQuery } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FieldSelect } from "@/components/ui/field-select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, useRegister } from "@/features/auth/use-auth";
import { locationsApi } from "@/features/auth/api";
import { registerSchema, type RegisterValues } from "@/features/auth/schemas";

export default function RegisterPage() {
  const router = useRouter();
  const registerMutation = useRegister();

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) });

  const statesQuery = useQuery({
    queryKey: ["locations", "states"],
    queryFn: locationsApi.listStates,
    staleTime: 24 * 60 * 60 * 1000,
  });

  const selectedStateCode = watch("state_code");
  const selectedState = statesQuery.data?.find((s) => s.code === selectedStateCode);
  const selectedStateId = selectedState?.id ?? null;

  const citiesQuery = useQuery({
    queryKey: ["locations", "cities", selectedStateId],
    queryFn: () => locationsApi.listCitiesForState(selectedStateId as string),
    enabled: !!selectedStateId,
    staleTime: 24 * 60 * 60 * 1000,
  });

  const onSubmit = (values: RegisterValues) => {
    registerMutation.mutate(values, {
      onSuccess: () => router.push("/student/dashboard"),
    });
  };

  const fieldErrors =
    registerMutation.error instanceof ApiError ? registerMutation.error.fieldErrors : {};

  return (
    <main className="flex flex-1 items-center justify-center px-6 py-12">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Create your account</CardTitle>
          <CardDescription>Start your NEET prep with Trinetra.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            {registerMutation.isError && (
              <Alert variant="destructive">
                <AlertDescription>
                  {registerMutation.error instanceof ApiError
                    ? registerMutation.error.message
                    : "Something went wrong"}
                  {registerMutation.error instanceof ApiError && registerMutation.error.code === "EMAIL_TAKEN" && (
                    <>
                      {" "}
                      <Link href="/login" className="underline underline-offset-2">
                        Sign in instead
                      </Link>
                    </>
                  )}
                </AlertDescription>
              </Alert>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="first_name">First name</Label>
              <Input
                id="first_name"
                autoComplete="given-name"
                aria-invalid={!!errors.first_name || !!fieldErrors.first_name}
                {...register("first_name")}
              />
              {(errors.first_name || fieldErrors.first_name) && (
                <p className="text-sm text-destructive">
                  {errors.first_name?.message ?? fieldErrors.first_name}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="last_name">Last name</Label>
              <Input
                id="last_name"
                autoComplete="family-name"
                aria-invalid={!!errors.last_name || !!fieldErrors.last_name}
                {...register("last_name")}
              />
              {(errors.last_name || fieldErrors.last_name) && (
                <p className="text-sm text-destructive">
                  {errors.last_name?.message ?? fieldErrors.last_name}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                aria-invalid={!!errors.email || !!fieldErrors.email}
                {...register("email")}
              />
              {(errors.email || fieldErrors.email) && (
                <p className="text-sm text-destructive">
                  {errors.email?.message ?? fieldErrors.email}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="mobile">Mobile number</Label>
              <Input
                id="mobile"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                placeholder="+91 98765 43210"
                aria-invalid={!!errors.mobile || !!fieldErrors.mobile}
                {...register("mobile")}
              />
              {(errors.mobile || fieldErrors.mobile) && (
                <p className="text-sm text-destructive">
                  {errors.mobile?.message ?? fieldErrors.mobile}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                10-digit Indian mobile. +91 or 0 prefix is optional.
              </p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="state_code">State / UT</Label>
              <FieldSelect
                id="state_code"
                autoComplete="address-level1"
                aria-invalid={!!errors.state_code || !!fieldErrors.state_code}
                aria-busy={statesQuery.isPending}
                disabled={statesQuery.isPending || statesQuery.isError}
                {...register("state_code", {
                  onChange: () => setValue("city", "", { shouldValidate: false }),
                })}
              >
                <option value="">
                  {statesQuery.isPending
                    ? "Loading states…"
                    : statesQuery.isError
                      ? "Could not load states"
                      : "Select your State / UT"}
                </option>
                {statesQuery.data?.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.name}
                  </option>
                ))}
              </FieldSelect>
              {(errors.state_code || fieldErrors.state_code) && (
                <p className="text-sm text-destructive">
                  {errors.state_code?.message ?? fieldErrors.state_code}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="city">City</Label>
              <FieldSelect
                id="city"
                autoComplete="address-level2"
                aria-invalid={!!errors.city || !!fieldErrors.city}
                aria-busy={citiesQuery.isFetching}
                disabled={!selectedStateId || citiesQuery.isPending || citiesQuery.isError}
                {...register("city")}
              >
                <option value="">
                  {!selectedStateId
                    ? "Select a State / UT first"
                    : citiesQuery.isPending
                      ? "Loading cities…"
                      : citiesQuery.isError
                        ? "Could not load cities"
                        : "Select your city"}
                </option>
                {citiesQuery.data?.map((c) => (
                  <option key={c.id} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </FieldSelect>
              {(errors.city || fieldErrors.city) && (
                <p className="text-sm text-destructive">
                  {errors.city?.message ?? fieldErrors.city}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                aria-invalid={!!errors.password || !!fieldErrors.password}
                {...register("password")}
              />
              {(errors.password || fieldErrors.password) && (
                <p className="text-sm text-destructive">
                  {errors.password?.message ?? fieldErrors.password}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                12+ characters, with uppercase, lowercase, a number, and a special character.
              </p>
            </div>
            <Button type="submit" disabled={registerMutation.isPending} className="mt-2">
              {registerMutation.isPending ? "Creating account…" : "Create account"}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="hover:underline">
              Sign in
            </Link>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
