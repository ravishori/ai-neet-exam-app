import { apiClient } from "@/lib/api-client";

export type Role = { id: string; code: string; name: string; description: string | null };

export const rolesApi = {
  list: () => apiClient.get<Role[]>("/api/v1/roles"),
};
