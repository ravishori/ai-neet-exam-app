"use client";

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { GoPremiumCard } from "@/components/go-premium-card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  PageHeader,
  StudentPage,
  SurfaceCard,
  SurfaceCardContent,
  SurfaceCardDescription,
  SurfaceCardHeader,
  SurfaceCardTitle,
} from "@/components/ds";
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

  return (
    <StudentPage width="md">
      <PageHeader eyebrow="Account" title="Profile" description="Keep your name and contact details up to date." />

      {isLoading ? (
        <Skeleton className="h-64 w-full rounded-2xl" aria-busy="true" />
      ) : (
        <div className="flex flex-col gap-4">
          <SurfaceCard accent="none">
            <SurfaceCardHeader>
              <SurfaceCardTitle>Your details</SurfaceCardTitle>
              <SurfaceCardDescription>{profile?.email}</SurfaceCardDescription>
            </SurfaceCardHeader>
            <SurfaceCardContent>
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
                <Button type="submit" size="touch" disabled={mutation.isPending} className="mt-2 w-fit">
                  {mutation.isPending ? "Saving…" : "Save changes"}
                </Button>
              </form>
            </SurfaceCardContent>
          </SurfaceCard>

          <GoPremiumCard />
        </div>
      )}
    </StudentPage>
  );
}
