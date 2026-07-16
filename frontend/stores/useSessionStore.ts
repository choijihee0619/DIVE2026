import { create } from "zustand";
import { clearSessionCookie, getSessionCookie, setSessionCookie } from "@/lib/session-cookie";
import type { UserPublic } from "@/types/auth";

interface SessionState {
  user: UserPublic | null;
  /** 쿠키에 토큰이 있는데 아직 user를 복원하지 못한 최초 렌더 구간(레이아웃 깜빡임 방지용). */
  isHydrating: boolean;
  setSession: (token: string, expiresInSeconds: number, user: UserPublic) => void;
  setUser: (user: UserPublic) => void;
  clearSession: () => void;
  setHydrating: (value: boolean) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  user: null,
  isHydrating: Boolean(typeof window !== "undefined" && getSessionCookie()),
  setSession: (token, expiresInSeconds, user) => {
    setSessionCookie(token, expiresInSeconds);
    set({ user, isHydrating: false });
  },
  setUser: (user) => set({ user, isHydrating: false }),
  clearSession: () => {
    clearSessionCookie();
    set({ user: null, isHydrating: false });
  },
  setHydrating: (value) => set({ isHydrating: value }),
}));
