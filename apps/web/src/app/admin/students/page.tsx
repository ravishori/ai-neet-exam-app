"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";
import { usersApi, type UserProfile } from "@/features/users/api";

const STATUS_OPTIONS = ["active", "suspended"];
const PAGE_SIZE = 20;

function StudentRow({ student }: { student: UserProfile }) {
  const queryClient = useQueryClient();
  const toggleStatus = useMutation({
    mutationFn: () =>
      usersApi.updateUser(student.id, { status: student.status === "active" ? "suspended" : "active" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["students", "list"] }),
  });

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-0.5">
          <Link href={`/admin/students/${student.id}`} className="font-medium underline-offset-4 hover:underline">
            {student.display_name ?? student.email}
          </Link>
          <p className="text-sm text-muted-foreground">{student.email}</p>
          <p className="text-xs text-muted-foreground">
            Registered {new Date(student.created_at).toLocaleDateString()}
            {student.last_login_at ? ` · Last login ${new Date(student.last_login_at).toLocaleDateString()}` : " · Never logged in"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!student.email_verified && <Badge variant="outline">Unverified</Badge>}
          <Badge variant={student.status === "active" ? "default" : "outline"}>{student.status}</Badge>
          <Button
            size="sm"
            variant="outline"
            disabled={toggleStatus.isPending}
            onClick={() => toggleStatus.mutate()}
          >
            {student.status === "active" ? "Suspend" : "Activate"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminStudentsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["students", "list", search, statusFilter, page],
    queryFn: () =>
      usersApi.list({
        search: search || undefined,
        status: statusFilter || undefined,
        role: "STUDENT",
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
  });

  if (error instanceof ApiError && error.code === "PERMISSION_DENIED") {
    return (
      <main className="flex-1 px-4 py-8 sm:px-6">
        <p className="text-sm text-muted-foreground">
          You don&apos;t have the <code>users.manage</code> permission needed to view student accounts.
        </p>
      </main>
    );
  }

  const students = data?.data ?? [];
  const total = data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <h1 className="font-heading text-xl font-semibold">Students</h1>
          <p className="text-sm text-muted-foreground">
            {total} student account{total === 1 ? "" : "s"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Input
            placeholder="Search by email…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="w-56"
          />
          <select
            className="h-9 rounded-md border bg-background px-2 text-sm"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-2" aria-busy="true" aria-live="polite">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </div>
        ) : students.length === 0 ? (
          <EmptyState title="No students found" description="Try adjusting your search or filters." />
        ) : (
          <div className="grid gap-3">
            {students.map((student) => (
              <StudentRow key={student.id} student={student} />
            ))}
          </div>
        )}

        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between">
            <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="size-4" aria-hidden="true" /> Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {page + 1} of {totalPages} · {total} total
            </span>
            <Button variant="outline" size="sm" disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)}>
              Next <ChevronRight className="size-4" aria-hidden="true" />
            </Button>
          </div>
        )}
      </div>
    </main>
  );
}
