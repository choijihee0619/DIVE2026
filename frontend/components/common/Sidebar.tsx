"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  FileText,
  Headset,
  LayoutDashboard,
  Link2,
  ListTodo,
  MessagesSquare,
  Settings,
  ShieldCheck,
  Siren,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { UserRole } from "@/types/enums";
import { BrandLogo } from "@/components/common/BrandLogo";

interface SidebarItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const SIDEBAR_ITEMS: Record<string, SidebarItem[]> = {
  [UserRole.TENANT]: [
    { href: "/tenant", label: "대시보드", icon: LayoutDashboard },
    { href: "/tenant/contracts", label: "내 계약", icon: FileText },
    { href: "/tenant/counsel", label: "AI 전세 상담", icon: MessagesSquare },
    { href: "/tenant/incidents", label: "사고 접수", icon: Siren },
    { href: "/notifications", label: "알림", icon: Bell },
  ],
  [UserRole.LANDLORD]: [
    { href: "/landlord", label: "대시보드", icon: LayoutDashboard },
    { href: "/notifications", label: "알림", icon: Bell },
  ],
  [UserRole.ADVISOR]: [
    { href: "/advisor", label: "상담 큐", icon: ListTodo },
    { href: "/advisor/verifications", label: "증빙 검증", icon: ShieldCheck },
    { href: "/advisor/counsel", label: "AI 상담 지원", icon: MessagesSquare },
    { href: "/notifications", label: "알림", icon: Bell },
  ],
  [UserRole.HUG_ADMIN]: [
    { href: "/hug/dashboard", label: "회수 코크핏", icon: LayoutDashboard },
    { href: "/hug/incidents", label: "사고 접수 큐", icon: Siren },
    { href: "/notifications", label: "알림", icon: Bell },
  ],
  [UserRole.SYSTEM_ADMIN]: [
    { href: "/admin", label: "사용자·권한 관리", icon: Users },
    { href: "/admin/blockchain", label: "블록체인 로그", icon: Link2 },
  ],
};

/** 역할별 "AI 상담" 헬프 카드의 이동 경로. 없으면 카드 숨김. */
const COUNSEL_ROUTE: Partial<Record<UserRole, string>> = {
  [UserRole.TENANT]: "/tenant/counsel",
  [UserRole.ADVISOR]: "/advisor/counsel",
};

interface SidebarProps {
  role: UserRole;
}

/** 260721 목업 공통 레이아웃의 흰색 사이드바 — 로고, 아이콘 메뉴, 하단 헬프 카드. */
export function Sidebar({ role }: SidebarProps) {
  const pathname = usePathname();
  const items = SIDEBAR_ITEMS[role] ?? [];
  const counselRoute = COUNSEL_ROUTE[role];
  if (items.length === 0) return null;

  return (
    <nav
      aria-label="사이드 메뉴"
      className="sticky top-0 hidden h-svh w-60 shrink-0 flex-col border-r border-line bg-sidebar px-4 pb-5 pt-6 md:flex"
    >
      <BrandLogo className="px-2" />
      <ul className="mt-8 flex flex-col gap-1">
        {items.map((item) => {
          const matches = (href: string) => pathname === href || pathname.startsWith(`${href}/`);
          /* 더 구체적인 다른 메뉴가 매칭되면 상위 경로 메뉴는 비활성(예: /tenant vs /tenant/contracts). */
          const active =
            matches(item.href) &&
            !items.some((other) => other.href.length > item.href.length && matches(other.href));
          const Icon = item.icon;
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-colors",
                  active
                    ? "bg-hug-sky text-hug-blue"
                    : "text-ink-soft hover:bg-neutral-100 hover:text-ink",
                )}
              >
                <Icon size={17} strokeWidth={active ? 2.4 : 2} />
                {item.label}
              </Link>
            </li>
          );
        })}
        <li>
          <span
            aria-disabled
            title="데모 범위 외"
            className="flex cursor-default items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold text-neutral-400"
          >
            <Settings size={17} strokeWidth={2} />
            설정
          </span>
        </li>
      </ul>

      {counselRoute ? (
        <div className="mt-auto rounded-2xl border border-line bg-neutral-100 p-4 text-center">
          <span className="mx-auto flex size-11 items-center justify-center rounded-full bg-hug-blue text-white">
            <Headset size={20} />
          </span>
          <p className="mt-3 text-sm font-bold">도움이 필요하신가요?</p>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            AI 상담 또는 고객센터를 통해
            <br />
            도움을 받으세요.
          </p>
          <Link
            href={counselRoute}
            className="mt-3 flex items-center justify-center gap-1 rounded-xl border border-line bg-card py-2 text-sm font-bold text-hug-blue transition-colors hover:bg-hug-sky"
          >
            AI 상담 시작 →
          </Link>
        </div>
      ) : (
        <div className="mt-auto flex items-center gap-2 rounded-2xl border border-line bg-neutral-100 p-4 text-xs text-muted-foreground">
          <ShieldCheck size={16} className="shrink-0 text-hug-green" />
          전세 생애주기 안심 플랫폼 · 안심루프
        </div>
      )}
    </nav>
  );
}
