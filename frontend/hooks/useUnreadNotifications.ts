"use client";

import { useCallback, useEffect, useState } from "react";
import { notificationService } from "@/services/notificationService";

/** 읽음 처리·시드 후 헤더 배지를 갱신시키기 위한 커스텀 이벤트 이름. */
export const NOTIFICATIONS_CHANGED_EVENT = "ansimloop:notifications-changed";

export function emitNotificationsChanged() {
  window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT));
}

/** 헤더 벨 배지용 미읽음 카운트. 마운트 시 + NOTIFICATIONS_CHANGED_EVENT 수신 시 갱신. */
export function useUnreadNotifications(enabled: boolean) {
  const [unreadCount, setUnreadCount] = useState(0);

  const refresh = useCallback(() => {
    if (!enabled) return;
    notificationService
      .list({ unreadOnly: true, size: 1 })
      .then((data) => setUnreadCount(data.unread_count))
      .catch(() => setUnreadCount(0));
  }, [enabled]);

  useEffect(() => {
    refresh();
    window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, refresh);
    return () => window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, refresh);
  }, [refresh]);

  return unreadCount;
}
