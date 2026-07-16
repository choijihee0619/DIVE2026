import { apiClient } from "@/services/apiClient";
import type { LoginData, LoginRequest, SignupRequest, UserPublic } from "@/types/auth";

export const authService = {
  login: (payload: LoginRequest) => apiClient.post<LoginData>("/auth/login", payload),
  signup: (payload: SignupRequest) => apiClient.post<UserPublic>("/auth/signup", payload),
  me: () => apiClient.get<UserPublic>("/auth/me"),
  logout: () => apiClient.post<{ logged_out: boolean }>("/auth/logout"),
};
