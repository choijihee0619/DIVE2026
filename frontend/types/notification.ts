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
  /** 예방 알림 연결 정보(§20.5 P3) — 계약별 필터·업무 확인에 사용. */
  contract_id?: string | null;
  target_role?: string | null;
  acknowledged_at?: string | null;
  created_at: string;
}

export interface NotificationListData {
  items: AppNotification[];
  unread_count: number;
  pagination: Pagination;
}
