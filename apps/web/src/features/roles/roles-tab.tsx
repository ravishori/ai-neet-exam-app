"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";

import { rolesApi, type Role } from "./api";
import { groupPermissions } from "./capability-labels";

/** Read-only, grouped human-readable view of a role's granted capabilities. */
function CapabilityView({ role }: { role: Role }) {
  const groups = groupPermissions(role.permission_codes);

  if (groups.length === 0) {
    return <p className="text-xs text-muted-foreground">No capabilities granted.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {groups.map(({ group, features }) => (
        <div key={group} className="flex flex-col gap-1">
          <p className="text-xs font-medium text-muted-foreground">{group}</p>
          <ul className="flex flex-col gap-0.5">
            {features.map(({ code, label }) => (
              <li key={code} className="flex items-center gap-1.5 text-sm">
                <span>{label.feature}</span>
                {!label.enforced && (
                  <Badge variant="outline" className="text-[10px]">
                    not yet enforced
                  </Badge>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/**
 * Shared between /admin/users (Roles & Permissions tab) and the dedicated
 * /admin/roles page — same underlying rolesApi, same SUPER_ADMIN-is-immutable
 * behavior (matches the server-side ROLE_IMMUTABLE guard in roles_router.py).
 */
function RolePermissionEditor({ role, allPermissions }: { role: Role; allPermissions: string[] }) {
  const queryClient = useQueryClient();
  const [codes, setCodes] = useState<string[]>(role.permission_codes);
  const [showTechnical, setShowTechnical] = useState(false);
  const isSuperAdmin = role.code === "SUPER_ADMIN";

  const save = useMutation({
    mutationFn: () => rolesApi.updatePermissions(role.id, codes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["roles", "list"] }),
  });

  const dirty = codes.slice().sort().join(",") !== role.permission_codes.slice().sort().join(",");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{role.name}</CardTitle>
        <CardDescription>{role.description ?? role.code}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {isSuperAdmin ? (
          <p className="text-xs text-muted-foreground">SUPER_ADMIN bypasses permission checks entirely — nothing to edit here.</p>
        ) : (
          <>
            <CapabilityView role={role} />

            <Button
              size="sm"
              variant="ghost"
              className="w-fit px-0 text-xs text-muted-foreground underline-offset-4 hover:underline"
              onClick={() => setShowTechnical((prev) => !prev)}
              aria-expanded={showTechnical}
            >
              {showTechnical ? "Hide technical permissions" : "Show technical permissions"}
            </Button>

            {showTechnical && (
              <>
                {save.isError && (
                  <Alert variant="destructive">
                    <AlertDescription>{save.error instanceof ApiError ? save.error.message : "Something went wrong"}</AlertDescription>
                  </Alert>
                )}
                <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
                  {allPermissions.map((code) => (
                    <label key={code} className="flex items-center gap-1.5 text-xs">
                      <input
                        type="checkbox"
                        checked={codes.includes(code)}
                        onChange={() => setCodes((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]))}
                      />
                      {code}
                    </label>
                  ))}
                </div>
                <Button size="sm" className="w-fit" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
                  {save.isPending ? "Saving…" : "Save permissions"}
                </Button>
              </>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function RolesTab() {
  const { data: roles, isLoading, error } = useQuery({ queryKey: ["roles", "list"], queryFn: rolesApi.list });
  const { data: permissions } = useQuery({ queryKey: ["roles", "permissions"], queryFn: rolesApi.listPermissions });

  const allPermissionCodes = permissions?.map((p) => p.code) ?? [];

  if (isLoading) {
    return <Skeleton className="h-96 w-full" aria-busy="true" aria-live="polite" />;
  }

  if (error instanceof ApiError && error.code === "PERMISSION_DENIED") {
    return (
      <p className="text-sm text-muted-foreground">
        You don&apos;t have the <code>users.manage</code> permission needed to view roles and permissions.
      </p>
    );
  }

  return (
    <div className="grid gap-3">
      {roles?.map((role) => (
        <RolePermissionEditor key={role.id} role={role} allPermissions={allPermissionCodes} />
      ))}
    </div>
  );
}
