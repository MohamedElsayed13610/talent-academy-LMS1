import { NextResponse, type NextRequest } from "next/server";

/**
 * Route guard only (docs/ARCHITECTURE.md §6.1). Redirects anonymous users to /login, admins to
 * /admin, students to /dashboard. The backend enforces every real permission itself on every
 * request — this never grants access, it only avoids a flash of the wrong shell.
 *
 * The access-token JWT is read without verifying its signature (this runs on the edge and never
 * makes a trust decision from it) — just enough to know the role for routing.
 */

// /design is reachable without logging in on purpose — it's the Phase 1 approval artifact
// (docs/ARCHITECTURE.md §6.1: "admin-only in production" is a later hardening step, not a Phase 1 gate).
const PUBLIC_PATHS = ["/", "/login", "/design"];

function decodeRole(token: string): "admin" | "student" | null {
  try {
    const [, payload] = token.split(".");
    if (!payload) return null;
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    return json.role === "admin" || json.role === "student" ? json.role : null;
  } catch {
    return null;
  }
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.includes(pathname) || pathname.startsWith("/api") || pathname.startsWith("/_next")) {
    return NextResponse.next();
  }

  const token = request.cookies.get("access_token")?.value;
  const role = token ? decodeRole(token) : null;

  if (!role) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }
  if (role === "admin" && !pathname.startsWith("/admin") && pathname !== "/change-password" && pathname !== "/design") {
    return NextResponse.redirect(new URL("/admin", request.url));
  }
  if (role === "student" && pathname.startsWith("/admin")) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|talent-logo.png).*)"],
};
