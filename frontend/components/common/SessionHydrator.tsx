"use client";

import { useEffect } from "react";
import { authService } from "@/services/authService";
import { getSessionCookie, clearSessionCookie } from "@/lib/session-cookie";
import { useSessionStore } from "@/stores/useSessionStore";

/**
 * 새로고침 등으로 Zustand 메모리 상태가 비어도 쿠키에 토큰이 남아있으면 /auth/me로
 * 사용자 정보를 복원한다. 최상위 Providers에서 한 번만 마운트한다.
 */
export function SessionHydrator() {
  const user = useSessionStore((state) => state.user);
  const setUser = useSessionStore((state) => state.setUser);
  const setHydrating = useSessionStore((state) => state.setHydrating);

  useEffect(() => {
    if (user) return;
    const token = getSessionCookie();
    if (!token) {
      setHydrating(false);
      return;
    }
    authService
      .me()
      .then((me) => setUser(me))
      .catch(() => {
        clearSessionCookie();
        setHydrating(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
