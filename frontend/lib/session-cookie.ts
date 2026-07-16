import Cookies from "js-cookie";

/**
 * 세션 JWT를 client-readable 쿠키에 저장한다(httpOnly 아님).
 * services/apiClient가 Authorization 헤더를 붙이려면 JS에서 읽을 수 있어야 하고,
 * middleware.ts도 동일 쿠키에서 role 클레임을 읽어 1차 라우트 가드를 수행한다.
 */
export const SESSION_COOKIE_NAME = "session";

export function setSessionCookie(token: string, expiresInSeconds: number) {
  Cookies.set(SESSION_COOKIE_NAME, token, {
    expires: expiresInSeconds / 86400,
    sameSite: "Lax",
    path: "/",
  });
}

export function getSessionCookie(): string | undefined {
  return Cookies.get(SESSION_COOKIE_NAME);
}

export function clearSessionCookie() {
  Cookies.remove(SESSION_COOKIE_NAME, { path: "/" });
}
