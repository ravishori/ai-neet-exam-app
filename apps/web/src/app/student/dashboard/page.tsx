"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMe } from "@/features/auth/use-auth";

export default function StudentDashboardPage() {
  const { data: user, isLoading } = useMe();

  return (
    <main className="flex flex-1 flex-col items-center gap-6 px-6 py-16">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">
          {isLoading ? "Loading…" : `Welcome, ${user?.first_name ?? user?.email}`}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Real widgets (mastery, revision queue, recommended practice) land once Academic +
          Assessment + Learning modules exist.
        </p>
      </div>
      {user && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-base">Account</CardTitle>
            <CardDescription>{user.email}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {user.roles.map((role) => (
              <Badge key={role} variant="secondary">
                {role}
              </Badge>
            ))}
            {!user.email_verified && <Badge variant="outline">Email not verified</Badge>}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
