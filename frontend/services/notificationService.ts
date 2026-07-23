import { apiClient } from "@/services/apiClient";
import type { AppNotification, NotificationListData } from "@/types/notification";

/** /notifications — 알림 목록·읽음 처리·데모 시드(COMMON-01). */
export const notificationService = {
  list: (params?: { unreadOnly?: boolean; page?: number; size?: number }) => {
    const query = new URLSearchParams();
    if (params?.unreadOnly) query.set("unread_only", "true");
    query.set("page", String(params?.page ?? 1));
    query.set("size", String(params?.size ?? 50));
    return apiClient.get<NotificationListData>(`/notifications?${query.toString()}`);
  },
  markRead: (notificationId: string) =>
    apiClient.patch<AppNotification>(`/notifications/${notificationId}/read`),
  /** 예방 알림 업무 확인(acknowledge) — 확인 시각이 3자 화면에 공유된다(§20.5 P3). */
  acknowledge: (notificationId: string) =>
    apiClient.patch<AppNotification>(`/notifications/${notificationId}/acknowledge`),
  markAllRead: () => apiClient.patch<{ updated: number }>("/notifications/read-all"),
  demoSeed: () => apiClient.post<{ created: number; items: AppNotification[] }>("/notifications/demo-seed"),
};
