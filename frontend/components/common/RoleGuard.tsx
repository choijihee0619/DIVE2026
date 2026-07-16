"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSessionStore } from "@/stores/useSessionStore";
import type { UserRole } from "@/types/enums";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";

interface RoleGuardProps {
  allowedRoles: UserRole[];
  children: React.ReactNode;
}

/**
 * middleware.ts가 1차로 라우트 진입을 막지만, 클라이언트 네비게이션(라우트 전환)이나
 * 세션 만료 등은 middleware를 다시 타지 않을 수 있어 2차로 한 번 더 확인한다(명세서 3장).
 */
export function RoleGuard({ allowedRoles, children }: RoleGuardProps) {
  const router = useRouter();
  const user = useSessionStore((state) => state.user);
  const isHydrating = useSessionStore((state) => state.isHydrating);

  useEffect(() => {
    if (isHydrating) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (!allowedRoles.includes(user.role)) {
      router.replace("/unauthorized");
    }
  }, [isHydrating, user, allowedRoles, router]);

  if (isHydrating || !user || !allowedRoles.includes(user.role)) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <LoadingSpinner label="확인 중..." />
      </div>
    );
  }

  return <>{children}</>;
}
