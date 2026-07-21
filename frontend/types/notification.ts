import type { Pagination } from "@/types/contract";

/** GET /notifications 응답(260721 실응답 기준). */
export interface AppNotification {
  notification_id: string;
  category: "registry_change" | "contract_event" | "deadline" | string;
  title: string;
  body: string;
  link: string | null;
  severity: "info" | "warning" | "danger" | string;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListData {
  items: AppNotification[];
  unread_count: number;
  pagination: Pagination;
}
