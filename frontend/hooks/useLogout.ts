import { useRouter } from "next/navigation";
import { authService } from "@/services/authService";
import { useSessionStore } from "@/stores/useSessionStore";

export function useLogout() {
  const router = useRouter();
  const clearSession = useSessionStore((state) => state.clearSession);

  return async () => {
    try {
      await authService.logout();
    } catch {
      // MVP: 서버측 토큰 블랙리스트가 없어 실패해도 클라이언트 세션은 정리한다(backend/README.md 9.1절).
    }
    clearSession();
    router.push("/login");
  };
}
