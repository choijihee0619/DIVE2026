"use client";

import { RoleGuard } from "@/components/common/RoleGuard";
import { Header } from "@/components/common/Header";
import { UserRole } from "@/types/enums";

const ALL_ROLES = Object.values(UserRole);

/** COMMON-01 알림 센터. 목록 연동은 /notifications API 확정 후 진행한다(명세서 5.24절). */
export default function NotificationsPage() {
  return (
    <RoleGuard allowedRoles={ALL_ROLES}>
      <div className="flex min-h-svh flex-col">
        <Header />
        <main className="flex-1 p-6">
          <h1 className="mb-4 text-lg font-semibold">알림 센터</h1>
          <p className="text-sm text-muted-foreground">새 알림이 없습니다.</p>
        </main>
      </div>
    </RoleGuard>
  );
}
