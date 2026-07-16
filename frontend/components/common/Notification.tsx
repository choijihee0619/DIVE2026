"use client";

import { cn } from "@/lib/utils";

export interface NotificationItem {
  notification_id: string;
  title: string;
  body: string;
  read: boolean;
  created_at: string;
  href?: string;
}

interface NotificationProps {
  notification: NotificationItem;
  onClick?: (notification: NotificationItem) => void;
}

export function Notification({ notification, onClick }: NotificationProps) {
  return (
    <button
      type="button"
      onClick={() => onClick?.(notification)}
      className={cn(
        "flex w-full flex-col gap-1 rounded-md border border-border px-3 py-2 text-left text-sm",
        notification.read ? "bg-card" : "bg-accent-100",
      )}
    >
      <span className="font-medium text-foreground">{notification.title}</span>
      <span className="text-muted-foreground">{notification.body}</span>
      <span className="text-xs text-muted-foreground">{notification.created_at}</span>
    </button>
  );
}
