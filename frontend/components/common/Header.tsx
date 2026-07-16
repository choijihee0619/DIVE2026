"use client";

import Link from "next/link";
import { Bell, LogOut, User as UserIcon } from "lucide-react";
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
import { ROLE_LABEL } from "@/lib/role-labels";

interface HeaderProps {
  /** 정적 목업. /notifications 실 연동은 COMMON-01 단계에서 진행한다(명세서 7.1절). */
  unreadCount?: number;
}

export function Header({ unreadCount = 0 }: HeaderProps) {
  const user = useSessionStore((state) => state.user);
  const logout = useLogout();

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-card px-4">
      <Link href={user ? "/" : "/login"} className="font-heading text-lg font-semibold text-foreground">
        HUG 안심전세 체인
      </Link>
      <div className="ml-auto flex items-center gap-2">
        <Link
          href="/notifications"
          aria-label={`알림${unreadCount > 0 ? ` (읽지 않음 ${unreadCount}건)` : ""}`}
          className={cn(buttonVariants({ variant: "ghost", size: "icon" }))}
        >
          <span className="relative inline-flex">
            <Bell size={18} />
            {unreadCount > 0 ? (
              <span
                className="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-danger-500 text-[9px] text-white"
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
                <Button variant="ghost" className="gap-2 px-1.5">
                  <Avatar size="sm">
                    <AvatarFallback>
                      <UserIcon size={14} />
                    </AvatarFallback>
                  </Avatar>
                  <span className="text-sm">{user.display_name}</span>
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
