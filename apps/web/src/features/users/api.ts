import { apiClient } from "@/lib/api-client";

export type UserProfile = {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  display_name: string | null;
  phone: string | null;
  status: string;
  email_verified: boolean;
  roles: string[];
  preferred_language: string;
  last_login_at: string | null;
  created_at: string;
};

export type UserUpdateInput = {
  first_name?: string;
  last_name?: string;
  display_name?: string;
  phone?: string;
  preferred_language?: string;
};

export type AdminUserUpdateInput = {
  status?: string;
  role_codes?: string[];
};

export type UserCreateInput = {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  role_codes?: string[];
};

export type UserListParams = {
  search?: string;
  status?: string;
  role?: string;
  limit?: number;
  offset?: number;
};

export type UserListResult = { data: UserProfile[]; meta: { total: number; limit: number; offset: number } };

export type BulkUserActionResult = { id: string; success: boolean; error?: string };

export const usersApi = {
  me: () => apiClient.get<UserProfile>("/api/v1/users/me"),
  updateMe: (data: UserUpdateInput) => apiClient.patch<UserProfile>("/api/v1/users/me", data),
  list: async (params: UserListParams = {}): Promise<UserListResult> => {
    const query = new URLSearchParams();
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    if (params.role) query.set("role", params.role);
    query.set("limit", String(params.limit ?? 50));
    query.set("offset", String(params.offset ?? 0));
    const body = await apiClient.getFull<UserProfile[]>(`/api/v1/users?${query.toString()}`);
    return { data: body.data ?? [], meta: body.meta as UserListResult["meta"] };
  },
  create: (data: UserCreateInput) => apiClient.post<UserProfile>("/api/v1/users", data),
  updateUser: (userId: string, data: AdminUserUpdateInput) =>
    apiClient.patch<UserProfile>(`/api/v1/users/${userId}`, data),
  bulkAction: (userIds: string[], action: "suspend" | "activate") =>
    apiClient.post<BulkUserActionResult[]>("/api/v1/users/bulk", { user_ids: userIds, action }),
};
