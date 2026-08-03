"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api-client";
import { rolesApi, type Role } from "@/features/roles/api";
import { usersApi, type UserProfile } from "@/features/users/api";

const STATUS_OPTIONS = ["active", "suspended"];
const PAGE_SIZE = 20;

function UserRow({
  user,
  allRoleCodes,
  selected,
  onToggleSelect,
}: {
  user: UserProfile;
  allRoleCodes: string[];
  selected: boolean;
  onToggleSelect: () => void;
}) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState(user.status);
  const [roleCodes, setRoleCodes] = useState<string[]>(user.roles);

  const dirty = status !== user.status || roleCodes.sort().join(",") !== [...user.roles].sort().join(",");

  const save = useMutation({
    mutationFn: () => usersApi.updateUser(user.id, { status, role_codes: roleCodes }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users", "list"] }),
  });

  const toggleRole = (code: string) => {
    setRoleCodes((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  return (
    <Card>
      <CardHeader className="flex-row items-center gap-3 space-y-0">
        <input type="checkbox" aria-label={`Select ${user.email}`} checked={selected} onChange={onToggleSelect} className="size-4" />
        <div className="flex flex-1 items-center justify-between">
          <div>
            <CardTitle className="text-base">{user.display_name ?? user.email}</CardTitle>
            <p className="text-sm text-muted-foreground">{user.email}</p>
          </div>
          <Badge variant={user.status === "active" ? "default" : "outline"}>{user.status}</Badge>
        </div>
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

function CreateUserForm({ allRoleCodes }: { allRoleCodes: string[] }) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roleCodes, setRoleCodes] = useState<string[]>([]);

  const create = useMutation({
    mutationFn: () => usersApi.create({ email, password, role_codes: roleCodes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users", "list"] });
      setEmail("");
      setPassword("");
      setRoleCodes([]);
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Create user</CardTitle>
        <CardDescription>Admin-created accounts skip self email verification.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {create.isError && (
          <Alert variant="destructive">
            <AlertDescription>{create.error instanceof ApiError ? create.error.message : "Something went wrong"}</AlertDescription>
          </Alert>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label>Email</Label>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Password</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Roles</Label>
          <div className="flex flex-wrap gap-3">
            {allRoleCodes.map((code) => (
              <label key={code} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={roleCodes.includes(code)}
                  onChange={() => setRoleCodes((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]))}
                />
                {code}
              </label>
            ))}
          </div>
        </div>
        <Button size="sm" className="w-fit" disabled={!email || !password || create.isPending} onClick={() => create.mutate()}>
          {create.isPending ? "Creating…" : "Create user"}
        </Button>
      </CardContent>
    </Card>
  );
}

function UsersTab() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["users", "list", search, statusFilter, roleFilter, page],
    queryFn: () => usersApi.list({ search: search || undefined, status: statusFilter || undefined, role: roleFilter || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
  });
  const { data: roles } = useQuery({ queryKey: ["roles", "list"], queryFn: rolesApi.list });

  const bulkAction = useMutation({
    mutationFn: (action: "suspend" | "activate") => usersApi.bulkAction(Array.from(selected), action),
    onSuccess: () => {
      setSelected(new Set());
      queryClient.invalidateQueries({ queryKey: ["users", "list"] });
    },
  });

  if (error instanceof ApiError && error.code === "PERMISSION_DENIED") {
    return (
      <p className="text-sm text-muted-foreground">
        You don&apos;t have the <code>users.manage</code> permission needed to view this page.
      </p>
    );
  }

  const allRoleCodes = roles?.map((r) => r.code) ?? [];
  const users = data?.data ?? [];
  const total = data?.meta.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <CreateUserForm allRoleCodes={allRoleCodes} />

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
        <select
          className="h-9 rounded-md border bg-background px-2 text-sm"
          value={roleFilter}
          onChange={(e) => {
            setRoleFilter(e.target.value);
            setPage(0);
          }}
        >
          <option value="">All roles</option>
          {allRoleCodes.map((code) => (
            <option key={code} value={code}>
              {code}
            </option>
          ))}
        </select>
        {selected.size > 0 && (
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{selected.size} selected</span>
            <Button size="sm" variant="outline" disabled={bulkAction.isPending} onClick={() => bulkAction.mutate("activate")}>
              Bulk activate
            </Button>
            <Button size="sm" variant="outline" disabled={bulkAction.isPending} onClick={() => bulkAction.mutate("suspend")}>
              Bulk suspend
            </Button>
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-2" aria-busy="true" aria-live="polite">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3">
          {users.map((user) => (
            <UserRow key={user.id} user={user} allRoleCodes={allRoleCodes} selected={selected.has(user.id)} onToggleSelect={() => toggleSelected(user.id)} />
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
  );
}

function RolePermissionEditor({ role, allPermissions }: { role: Role; allPermissions: string[] }) {
  const queryClient = useQueryClient();
  const [codes, setCodes] = useState<string[]>(role.permission_codes);
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
      </CardContent>
    </Card>
  );
}

function RolesTab() {
  const { data: roles, isLoading } = useQuery({ queryKey: ["roles", "list"], queryFn: rolesApi.list });
  const { data: permissions } = useQuery({ queryKey: ["roles", "permissions"], queryFn: rolesApi.listPermissions });

  const allPermissionCodes = permissions?.map((p) => p.code) ?? [];

  if (isLoading) {
    return <Skeleton className="h-96 w-full" aria-busy="true" aria-live="polite" />;
  }

  return (
    <div className="grid gap-3">
      {roles?.map((role) => (
        <RolePermissionEditor key={role.id} role={role} allPermissions={allPermissionCodes} />
      ))}
    </div>
  );
}

export default function AdminUsersPage() {
  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <h1 className="font-heading text-xl font-semibold">Users & Roles</h1>

        <Tabs defaultValue="users">
          <TabsList>
            <TabsTrigger value="users">Users</TabsTrigger>
            <TabsTrigger value="roles">Roles & Permissions</TabsTrigger>
          </TabsList>
          <TabsContent value="users" className="mt-4">
            <UsersTab />
          </TabsContent>
          <TabsContent value="roles" className="mt-4">
            <RolesTab />
          </TabsContent>
        </Tabs>
      </div>
    </main>
  );
}
