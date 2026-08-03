"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { adminApi } from "@/features/admin/api";

const PAGE_SIZE = 50;

export default function AuditLogsPage() {
  const [actionFilter, setActionFilter] = useState("");
  const [entityTypeFilter, setEntityTypeFilter] = useState("");
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["admin", "audit-logs", actionFilter, entityTypeFilter, page],
    queryFn: () =>
      adminApi.auditLogs({
        action: actionFilter || undefined,
        entityType: entityTypeFilter || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
  });

  const entries = data?.data ?? [];
  const total = data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div>
          <h1 className="font-heading text-xl font-semibold">Audit Logs</h1>
          <p className="text-sm text-muted-foreground">Every admin action recorded: who, what, and when.</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="Filter by action (e.g. content.publish)…"
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(0);
            }}
            className="w-64"
          />
          <Input
            placeholder="Filter by entity type…"
            value={entityTypeFilter}
            onChange={(e) => {
              setEntityTypeFilter(e.target.value);
              setPage(0);
            }}
            className="w-56"
          />
        </div>

        {isLoading ? (
          <Skeleton className="h-96 w-full" aria-busy="true" aria-live="polite" />
        ) : entries.length === 0 ? (
          <EmptyState title="No audit entries match this filter" />
        ) : (
          <div className="overflow-x-auto rounded-md border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity</TableHead>
                  <TableHead>IP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entries.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{new Date(entry.created_at).toLocaleString()}</TableCell>
                    <TableCell className="text-sm">{entry.actor_email ?? entry.actor_user_id ?? "system"}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{entry.action}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {entry.entity_type ? `${entry.entity_type}${entry.entity_id ? ` · ${entry.entity_id.slice(0, 8)}…` : ""}` : "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{entry.ip_address ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
