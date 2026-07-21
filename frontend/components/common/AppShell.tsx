"use client";

import { RoleGuard } from "@/components/common/RoleGuard";
import { Header } from "@/components/common/Header";
import { Sidebar } from "@/components/common/Sidebar";
import type { UserRole } from "@/types/enums";

interface AppShellProps {
  allowedRoles: UserRole[];
  children: React.ReactNode;
}

/** role별 layout.tsx가 공통으로 쓰는 골격: 전역 사이드바 + (헤더 + 본문) 우측 칼럼. */
export function AppShell({ allowedRoles, children }: AppShellProps) {
  return (
    <RoleGuard allowedRoles={allowedRoles}>
      <div className="flex min-h-svh">
        <Sidebar role={allowedRoles[0]} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <main className="mx-auto w-full max-w-6xl flex-1 px-6 pb-12 pt-2">{children}</main>
        </div>
      </div>
    </RoleGuard>
  );
}
