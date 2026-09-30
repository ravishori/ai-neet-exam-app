"use client";

import { RolesTab } from "@/features/roles/roles-tab";

export default function AdminRolesPage() {
  return (
    <main className="flex-1 px-4 py-8 sm:px-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <div>
          <h1 className="font-heading text-xl font-semibold">Roles & Permissions</h1>
          <p className="text-sm text-muted-foreground">
            SUPER_ADMIN bypasses all permission checks and cannot be edited here.
          </p>
        </div>
        <RolesTab />
      </div>
    </main>
  );
}
