"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  BellRing,
  CalendarClock,
  Check,
  CheckCheck,
  FileSignature,
  ScrollText,
  Sparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { RoleGuard } from "@/components/common/RoleGuard";
import { Header } from "@/components/common/Header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { UserRole } from "@/types/enums";
import { notificationService } from "@/services/notificationService";
import { emitNotificationsChanged } from "@/hooks/useUnreadNotifications";
import type { AppNotification } from "@/types/notification";
import { cn } from "@/lib/utils";

const ALL_ROLES = Object.values(UserRole);

const CATEGORY_STYLE: Record<string, { icon: LucideIcon; label: string }> = {
  registry_change: { icon: ScrollText, label: "등기 변동" },
  contract_event: { icon: FileSignature, label: "계약 이벤트" },
  deadline: { icon: CalendarClock, label: "기한 알림" },
};

const SEVERITY_TONE: Record<string, string> = {
  info: "bg-hug-sky text-hug-blue",
  warning: "bg-warning-100 text-warning-700",
  danger: "bg-danger-100 text-danger-600",
};

function timeLabel(iso: string) {
  return new Date(iso).toLocaleString("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** COMMON-01 알림 센터 — GET /notifications + 읽음 처리 + 데모 시드 실연동. */
export default function NotificationsPage() {
  const [items, setItems] = useState<AppNotification[] | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(() => {
    notificationService
      .list({ size: 50 })
      .then((data) => {
        setItems(data.items);
        setUnreadCount(data.unread_count);
        setErrorMessage(null);
      })
      .catch(() => setErrorMessage("알림을 불러오지 못했습니다."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const markRead = (notification: AppNotification) => {
    if (notification.is_read) return;
    notificationService
      .markRead(notification.notification_id)
      .then(() => {
        setItems((prev) =>
          (prev ?? []).map((n) =>
            n.notification_id === notification.notification_id ? { ...n, is_read: true } : n,
          ),
        );
        setUnreadCount((count) => Math.max(0, count - 1));
        emitNotificationsChanged();
      })
      .catch(() => toast.error("읽음 처리에 실패했습니다."));
  };

  const markAllRead = () => {
    notificationService
      .markAllRead()
      .then(() => {
        setItems((prev) => (prev ?? []).map((n) => ({ ...n, is_read: true })));
        setUnreadCount(0);
        emitNotificationsChanged();
        toast.success("모든 알림을 읽음 처리했습니다.");
      })
      .catch(() => toast.error("읽음 처리에 실패했습니다."));
  };

  const seedDemo = () => {
    setSeeding(true);
    notificationService
      .demoSeed()
      .then((result) => {
        toast.success(`데모 알림 ${result.created}건이 생성되었습니다.`);
        load();
        emitNotificationsChanged();
      })
      .catch(() => toast.error("데모 알림 생성에 실패했습니다."))
      .finally(() => setSeeding(false));
  };

  return (
    <RoleGuard allowedRoles={ALL_ROLES}>
      <div className="flex min-h-svh flex-col">
        <Header />
        <main className="mx-auto w-full max-w-3xl flex-1 px-6 pb-12 pt-2">
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-extrabold tracking-tight">
                알림 센터
                {unreadCount > 0 ? (
                  <span className="rounded-full bg-danger-100 px-2.5 py-0.5 text-xs font-bold text-danger-600 tnum">
                    미읽음 {unreadCount}
                  </span>
                ) : null}
              </h1>
              <p className="mt-1.5 text-muted-foreground">등기 변동·계약 이벤트·보증 만기를 실시간으로 알려드려요.</p>
            </div>
            <div className="ml-auto flex gap-2">
              <Button variant="outline" size="sm" className="rounded-full" onClick={seedDemo} disabled={seeding}>
                <Sparkles size={14} />
                {seeding ? "생성 중..." : "데모 알림 생성"}
              </Button>
              <Button
                size="sm"
                className="rounded-full"
                onClick={markAllRead}
                disabled={!items || unreadCount === 0}
              >
                <CheckCheck size={14} />
                모두 읽음
              </Button>
            </div>
          </div>

          {errorMessage ? (
            <Card className="rounded-2xl border-line">
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
                <p className="text-sm text-destructive">{errorMessage}</p>
                <Button variant="outline" onClick={load}>
                  다시 시도
                </Button>
              </CardContent>
            </Card>
          ) : items === null ? (
            <div className="flex flex-col gap-2" aria-label="알림 불러오는 중">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-2xl" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <Card className="rounded-2xl border-line">
              <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
                <span className="flex size-12 items-center justify-center rounded-full bg-hug-sky text-hug-blue">
                  <BellRing size={22} />
                </span>
                <p className="text-sm font-semibold">새 알림이 없습니다.</p>
                <p className="text-xs text-muted-foreground">
                  &ldquo;데모 알림 생성&rdquo;으로 등기 변동·만기 알림 시나리오를 시연할 수 있어요.
                </p>
              </CardContent>
            </Card>
          ) : (
            <ul className="flex flex-col gap-2.5">
              <AnimatePresence initial={false}>
                {items.map((notification, index) => {
                  const category = CATEGORY_STYLE[notification.category] ?? {
                    icon: BellRing,
                    label: "알림",
                  };
                  const Icon = category.icon;
                  return (
                    <motion.li
                      key={notification.notification_id}
                      initial={{ opacity: 0, y: 14 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.35, delay: index * 0.05, ease: "easeOut" }}
                    >
                      <Card
                        className={cn(
                          "rounded-2xl border-line transition-colors",
                          notification.is_read ? "opacity-70" : "shadow-card",
                        )}
                      >
                        <CardContent className="flex items-start gap-3.5 py-4">
                          <span
                            className={cn(
                              "mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl",
                              SEVERITY_TONE[notification.severity] ?? SEVERITY_TONE.info,
                            )}
                          >
                            <Icon size={17} />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              {!notification.is_read ? (
                                <span className="size-2 shrink-0 rounded-full bg-danger-500" aria-label="미읽음" />
                              ) : null}
                              <p className="truncate text-sm font-bold">{notification.title}</p>
                              <span className="ml-auto shrink-0 text-[11px] text-muted-foreground tnum">
                                {timeLabel(notification.created_at)}
                              </span>
                            </div>
                            <p className="mt-0.5 text-sm text-muted-foreground">{notification.body}</p>
                            <div className="mt-1.5 flex items-center gap-3 text-xs">
                              <span className="rounded-full bg-neutral-200 px-2 py-0.5 font-semibold text-neutral-700">
                                {category.label}
                              </span>
                              {notification.link ? (
                                <Link
                                  href={notification.link}
                                  className="font-semibold text-hug-blue underline underline-offset-2"
                                >
                                  바로가기 →
                                </Link>
                              ) : null}
                              {!notification.is_read ? (
                                <button
                                  type="button"
                                  onClick={() => markRead(notification)}
                                  className="ml-auto flex items-center gap-1 font-semibold text-muted-foreground hover:text-foreground"
                                >
                                  <Check size={13} />
                                  읽음
                                </button>
                              ) : null}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    </motion.li>
                  );
                })}
              </AnimatePresence>
            </ul>
          )}
        </main>
      </div>
    </RoleGuard>
  );
}
