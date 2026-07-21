"use client";

import Link from "next/link";
import { Bell, ChevronDown, LogOut, User as UserIcon } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useSessionStore } from "@/stores/useSessionStore";
import { useLogout } from "@/hooks/useLogout";
import { useUnreadNotifications } from "@/hooks/useUnreadNotifications";
import { ROLE_LABEL } from "@/lib/role-labels";
import { BrandLogo } from "@/components/common/BrandLogo";

/** 우측 상단 알림 벨(GET /notifications 미읽음 실카운트) + 프로필 드롭다운. 로고는 데스크톱에선 사이드바가 담당. */
export function Header() {
  const user = useSessionStore((state) => state.user);
  const logout = useLogout();
  const unreadCount = useUnreadNotifications(Boolean(user));

  return (
    <header className="flex h-16 shrink-0 items-center gap-4 px-6">
      <span className="md:hidden">
        <BrandLogo href={user ? "/" : "/login"} />
      </span>
      <div className="ml-auto flex items-center gap-1.5">
        <Link
          href="/notifications"
          aria-label={`알림${unreadCount > 0 ? ` (읽지 않음 ${unreadCount}건)` : ""}`}
          className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "rounded-full")}
        >
          <span className="relative inline-flex">
            <Bell size={19} />
            {unreadCount > 0 ? (
              <span
                className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-danger-500 text-[9px] font-bold text-white"
                aria-hidden="true"
              >
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            ) : null}
          </span>
        </Link>
        {user ? (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" className="gap-2 rounded-full px-2">
                  <Avatar size="sm">
                    <AvatarFallback className="bg-hug-sky text-hug-blue">
                      <UserIcon size={14} />
                    </AvatarFallback>
                  </Avatar>
                  <span className="text-sm font-semibold">{user.display_name}</span>
                  <ChevronDown size={14} className="text-muted-foreground" />
                </Button>
              }
            />
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>{ROLE_LABEL[user.role]}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout} variant="destructive">
                <LogOut size={14} />
                로그아웃
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
    </header>
  );
}
