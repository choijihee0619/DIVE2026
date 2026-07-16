"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { UserRole } from "@/types/enums";

interface SidebarItem {
  href: string;
  label: string;
}

const SIDEBAR_ITEMS: Record<string, SidebarItem[]> = {
  [UserRole.ADVISOR]: [
    { href: "/advisor", label: "상담 큐" },
    { href: "/advisor/counsel", label: "AI 상담 지원" },
  ],
  [UserRole.HUG_ADMIN]: [
    { href: "/hug/dashboard", label: "채권관리 대시보드" },
  ],
  [UserRole.SYSTEM_ADMIN]: [
    { href: "/admin", label: "사용자·권한 관리" },
    { href: "/admin/api-status", label: "외부 API/모델 상태" },
    { href: "/admin/blockchain", label: "블록체인 로그" },
    { href: "/admin/logs", label: "시스템 로그" },
  ],
};

interface SidebarProps {
  role: UserRole;
}

/** HUG/아이엔/관리자 화면에서만 사용한다(명세서 7.1절: tenant/landlord는 Header 중심 레이아웃). */
export function Sidebar({ role }: SidebarProps) {
  const pathname = usePathname();
  const items = SIDEBAR_ITEMS[role] ?? [];
  if (items.length === 0) return null;

  return (
    <nav aria-label="사이드 메뉴" className="w-56 shrink-0 border-r border-border bg-card p-3">
      <ul className="flex flex-col gap-0.5">
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "block rounded-md px-2.5 py-1.5 text-sm text-foreground",
                  active ? "bg-primary text-primary-foreground" : "hover:bg-accent-100",
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
