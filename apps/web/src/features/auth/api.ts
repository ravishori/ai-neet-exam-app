import { apiClient } from "@/lib/api-client";

export type MeResponse = {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  display_name: string | null;
  email_verified: boolean;
  roles: string[];
};

export const authApi = {
  me: () => apiClient.get<MeResponse>("/api/v1/auth/me"),
  login: (data: { email: string; password: string }) =>
    apiClient.post<MeResponse>("/api/v1/auth/login", data),
  register: (data: { email: string; password: string; first_name?: string; last_name?: string }) =>
    apiClient.post<MeResponse>("/api/v1/auth/register", data),
  logout: () => apiClient.post<{ loggedOut: boolean }>("/api/v1/auth/logout"),
  forgotPassword: (data: { email: string }) =>
    apiClient.post<{ message: string }>("/api/v1/auth/forgot-password", data),
  resetPassword: (data: { token: string; new_password: string }) =>
    apiClient.post<{ message: string }>("/api/v1/auth/reset-password", data),
  verifyEmail: (data: { token: string }) =>
    apiClient.post<MeResponse>("/api/v1/auth/verify-email", data),
};
