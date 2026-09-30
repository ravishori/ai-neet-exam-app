"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";
import { usersApi } from "@/features/users/api";

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm">{value ?? "—"}</dd>
    </div>
  );
}

export default function StudentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["students", "detail", id],
    queryFn: () => usersApi.get(id),
    retry: (failureCount, error) => (error instanceof ApiError && error.status === 404 ? false : failureCount < 2),
  });

  const toggleStatus = useMutation({
    mutationFn: () =>
      usersApi.updateUser(id, { status: query.data?.status === "active" ? "suspended" : "active" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["students", "detail", id] });
      queryClient.invalidateQueries({ queryKey: ["students", "list"] });
    },
  });

  const notFound = query.isError && query.error instanceof ApiError && query.error.status === 404;
  const forbidden = query.isError && query.error instanceof ApiError && query.error.code === "PERMISSION_DENIED";
  const student = query.data;

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
          <Link href="/admin/students" className="underline-offset-4 hover:underline">
            &larr; Back to Students
          </Link>
        </nav>

        {query.isLoading && <Skeleton className="h-64 w-full" aria-busy="true" aria-live="polite" />}
        {notFound && <EmptyState title="Student not found" />}
        {forbidden && (
          <p className="text-sm text-muted-foreground">
            You don&apos;t have the <code>users.manage</code> permission needed to view this student.
          </p>
        )}

        {student && (
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>{student.display_name ?? student.email}</CardTitle>
                  <p className="text-sm text-muted-foreground">{student.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  {!student.email_verified && <Badge variant="outline">Unverified</Badge>}
                  <Badge variant={student.status === "active" ? "default" : "outline"}>{student.status}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <dl className="grid grid-cols-2 gap-4">
                <Field label="First name" value={student.first_name} />
                <Field label="Last name" value={student.last_name} />
                <Field label="Phone" value={student.phone} />
                <Field label="Mobile" value={student.mobile_e164} />
                <Field label="State" value={student.state_code} />
                <Field label="City" value={student.city_name} />
                <Field label="Preferred language" value={student.preferred_language} />
                <Field
                  label="Registered"
                  value={new Date(student.created_at).toLocaleString()}
                />
                <Field
                  label="Last login"
                  value={student.last_login_at ? new Date(student.last_login_at).toLocaleString() : "Never"}
                />
              </dl>

              <div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={toggleStatus.isPending}
                  onClick={() => toggleStatus.mutate()}
                >
                  {toggleStatus.isPending
                    ? "Saving…"
                    : student.status === "active"
                      ? "Suspend account"
                      : "Activate account"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}
