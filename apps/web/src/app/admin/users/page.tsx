"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api-client";
import { usersApi } from "@/features/users/api";

export default function AdminUsersPage() {
  const { data: users, isLoading, error } = useQuery({ queryKey: ["users", "list"], queryFn: usersApi.list });

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

  return (
    <main className="flex-1 px-6 py-10">
      <h1 className="mb-6 text-xl font-semibold">Users</h1>
      <div className="grid gap-3">
        {users?.map((user) => (
          <Card key={user.id}>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle className="text-base">{user.display_name ?? user.email}</CardTitle>
                <p className="text-sm text-muted-foreground">{user.email}</p>
              </div>
              <Badge variant={user.status === "active" ? "default" : "outline"}>{user.status}</Badge>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {user.roles.map((role) => (
                <Badge key={role} variant="secondary">
                  {role}
                </Badge>
              ))}
              {!user.email_verified && <Badge variant="outline">Unverified</Badge>}
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
