import { apiClient } from "@/lib/api-client";

export type Role = { id: string; code: string; name: string; description: string | null; permission_codes: string[] };
export type Permission = { code: string; description: string | null };

export const rolesApi = {
  list: () => apiClient.get<Role[]>("/api/v1/roles"),
  listPermissions: () => apiClient.get<Permission[]>("/api/v1/roles/permissions"),
  updatePermissions: (roleId: string, permissionCodes: string[]) =>
    apiClient.patch<Role>(`/api/v1/roles/${roleId}/permissions`, { permission_codes: permissionCodes }),
};
