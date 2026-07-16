"use client";

import { RoleGuard } from "@/components/common/RoleGuard";
import { Header } from "@/components/common/Header";
import { Sidebar } from "@/components/common/Sidebar";
import type { UserRole } from "@/types/enums";

interface AppShellProps {
  allowedRoles: UserRole[];
  children: React.ReactNode;
}

/** role별 layout.tsx가 공통으로 쓰는 골격: Header + (역할에 따라) Sidebar + RoleGuard. */
export function AppShell({ allowedRoles, children }: AppShellProps) {
  return (
    <RoleGuard allowedRoles={allowedRoles}>
      <div className="flex min-h-svh flex-col">
        <Header />
        <div className="flex flex-1">
          <Sidebar role={allowedRoles[0]} />
          <main className="flex-1 p-6">{children}</main>
        </div>
      </div>
    </RoleGuard>
  );
}
