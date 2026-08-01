"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { GoPremiumCard } from "@/components/go-premium-card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ME_QUERY_KEY } from "@/features/auth/use-auth";
import { usersApi, type UserUpdateInput } from "@/features/users/api";

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const { data: profile, isLoading } = useQuery({ queryKey: ["users", "me"], queryFn: usersApi.me });

  const { register, handleSubmit, reset } = useForm<UserUpdateInput>();

  useEffect(() => {
    if (profile) {
      reset({
        first_name: profile.first_name ?? "",
        last_name: profile.last_name ?? "",
        display_name: profile.display_name ?? "",
        phone: profile.phone ?? "",
      });
    }
  }, [profile, reset]);

  const mutation = useMutation({
    mutationFn: usersApi.updateMe,
    onSuccess: (updated) => {
      queryClient.setQueryData(["users", "me"], updated);
      queryClient.setQueryData(ME_QUERY_KEY, updated);
    },
  });

  if (isLoading) return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;

  return (
    <main className="flex flex-1 justify-center px-6 py-12">
      <div className="flex w-full max-w-lg flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>{profile?.email}</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit((values) => mutation.mutate(values))} className="flex flex-col gap-4">
              {mutation.isSuccess && (
                <Alert>
                  <AlertDescription>Saved.</AlertDescription>
                </Alert>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="first_name">First name</Label>
                  <Input id="first_name" {...register("first_name")} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="last_name">Last name</Label>
                  <Input id="last_name" {...register("last_name")} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="display_name">Display name</Label>
                <Input id="display_name" {...register("display_name")} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="phone">Phone</Label>
                <Input id="phone" {...register("phone")} />
              </div>
              <Button type="submit" disabled={mutation.isPending} className="mt-2 w-fit">
                {mutation.isPending ? "Saving…" : "Save changes"}
              </Button>
            </form>
          </CardContent>
        </Card>

        <GoPremiumCard />
      </div>
    </main>
  );
}
