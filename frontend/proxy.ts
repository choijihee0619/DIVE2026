import { NextResponse, type NextRequest } from "next/server";
import { decodeJwt } from "jose";
import { SESSION_COOKIE_NAME } from "@/lib/session-cookie";
import { ROUTE_GROUP_ROLES, type UserRole } from "@/types/enums";

const PROTECTED_PREFIXES = Object.keys(ROUTE_GROUP_ROLES);

function matchProtectedPrefix(pathname: string): string | null {
  return PROTECTED_PREFIXES.find((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)) ?? null;
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const prefix = matchProtectedPrefix(pathname);
  if (!prefix) return NextResponse.next();

  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  try {
    const payload = decodeJwt(token) as { role?: string; exp?: number };
    const now = Math.floor(Date.now() / 1000);
    if (payload.exp && payload.exp < now) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("next", pathname);
      return NextResponse.redirect(loginUrl);
    }

    const allowedRoles = ROUTE_GROUP_ROLES[prefix];
    if (!payload.role || !allowedRoles.includes(payload.role as UserRole)) {
      return NextResponse.redirect(new URL("/unauthorized", request.url));
    }
  } catch {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/tenant/:path*", "/landlord/:path*", "/advisor/:path*", "/hug/:path*", "/admin/:path*"],
};
