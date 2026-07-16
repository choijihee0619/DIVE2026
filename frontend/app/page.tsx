"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSessionStore } from "@/stores/useSessionStore";
import { ROLE_HOME_ROUTE } from "@/types/enums";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";

export default function RootPage() {
  const router = useRouter();
  const user = useSessionStore((state) => state.user);
  const isHydrating = useSessionStore((state) => state.isHydrating);

  useEffect(() => {
    if (isHydrating) return;
    router.replace(user ? ROLE_HOME_ROUTE[user.role] : "/login");
  }, [isHydrating, user, router]);

  return (
    <main className="flex min-h-svh items-center justify-center">
      <LoadingSpinner label="이동 중..." />
    </main>
  );
}
