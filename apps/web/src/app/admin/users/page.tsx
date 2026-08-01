"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api-client";
import { rolesApi } from "@/features/roles/api";
import { usersApi, type UserProfile } from "@/features/users/api";

const STATUS_OPTIONS = ["active", "suspended"];

function UserRow({ user, allRoleCodes }: { user: UserProfile; allRoleCodes: string[] }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState(user.status);
  const [roleCodes, setRoleCodes] = useState<string[]>(user.roles);

  const dirty = status !== user.status || roleCodes.sort().join(",") !== [...user.roles].sort().join(",");

  const save = useMutation({
    mutationFn: () => usersApi.updateUser(user.id, { status, role_codes: roleCodes }),
    onSuccess: (updated) => {
      queryClient.setQueryData<UserProfile[]>(["users", "list"], (prev) =>
        prev?.map((u) => (u.id === updated.id ? updated : u))
      );
    },
  });

  const toggleRole = (code: string) => {
    setRoleCodes((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-base">{user.display_name ?? user.email}</CardTitle>
          <p className="text-sm text-muted-foreground">{user.email}</p>
        </div>
        <Badge variant={user.status === "active" ? "default" : "outline"}>{user.status}</Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {save.isError && (
          <Alert variant="destructive">
            <AlertDescription>{save.error instanceof ApiError ? save.error.message : "Something went wrong"}</AlertDescription>
          </Alert>
        )}
        <div className="flex flex-col gap-1.5">
          <Label>Status</Label>
          <select
            className="h-9 w-40 rounded-md border bg-background px-2 text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Roles</Label>
          <div className="flex flex-wrap gap-3">
            {allRoleCodes.map((code) => (
              <label key={code} className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" checked={roleCodes.includes(code)} onChange={() => toggleRole(code)} />
                {code}
              </label>
            ))}
          </div>
        </div>
        {!user.email_verified && <Badge variant="outline">Unverified</Badge>}
        <Button size="sm" className="w-fit" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save"}
        </Button>
      </CardContent>
    </Card>
  );
}

export default function AdminUsersPage() {
  const { data: users, isLoading, error } = useQuery({ queryKey: ["users", "list"], queryFn: usersApi.list });
  const { data: roles } = useQuery({ queryKey: ["roles", "list"], queryFn: rolesApi.list });

  if (isLoading) {
    return <main className="flex-1 px-6 py-12 text-center text-sm text-muted-foreground">Loading…</main>;
  }

  if (error instanceof ApiError && error.code === "PERMISSION_DENIED") {
    return (
      <main className="flex flex-1 items-center justify-center px-6 text-center">
        <p className="text-sm text-muted-foreground">
          You don&apos;t have the <code>users.manage</code> permission needed to view this page.
        </p>
      </main>
    );
  }

  const allRoleCodes = roles?.map((r) => r.code) ?? [];

  return (
    <main className="flex-1 px-6 py-10">
      <h1 className="mb-6 text-xl font-semibold">Users</h1>
      <div className="grid gap-3">
        {users?.map((user) => (
          <UserRow key={user.id} user={user} allRoleCodes={allRoleCodes} />
        ))}
      </div>
    </main>
  );
}
