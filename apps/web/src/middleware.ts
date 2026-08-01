import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Presence-only check — this is a UX redirect, not the security boundary.
// Every API call is still authorized server-side on every request.
const PROTECTED_PREFIXES = ["/student", "/admin"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));

  if (isProtected && !request.cookies.get("access_token")) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/student/:path*", "/admin/:path*"],
};
