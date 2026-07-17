import { apiClient } from "@/services/apiClient";
import type { Pagination } from "@/types/contract";
import type { UserPublic } from "@/types/auth";

export const adminService = {
  /** GET /admin/users — system_admin 전용. */
  listUsers: (size = 100) =>
    apiClient.get<{ items: UserPublic[]; pagination: Pagination }>(`/admin/users?page=1&size=${size}`),
};
