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
  last_login_at: string | null;
  created_at: string;
};

export type UserUpdateInput = {
  first_name?: string;
  last_name?: string;
  display_name?: string;
  phone?: string;
};

export type AdminUserUpdateInput = {
  status?: string;
  role_codes?: string[];
};

export const usersApi = {
  me: () => apiClient.get<UserProfile>("/api/v1/users/me"),
  updateMe: (data: UserUpdateInput) => apiClient.patch<UserProfile>("/api/v1/users/me", data),
  list: () => apiClient.get<UserProfile[]>("/api/v1/users"),
  updateUser: (userId: string, data: AdminUserUpdateInput) =>
    apiClient.patch<UserProfile>(`/api/v1/users/${userId}`, data),
};
