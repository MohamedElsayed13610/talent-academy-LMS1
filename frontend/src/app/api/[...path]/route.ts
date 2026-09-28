import { type NextRequest, NextResponse } from "next/server";

/**
 * Same-origin proxy to the backend (docs/ARCHITECTURE.md §1). The browser only ever calls
 * /api/v1/* on this origin; this route forwards to BACKEND_INTERNAL_URL (the backend's private
 * Railway address, or the docker-compose "backend" service name in dev) and streams the body and
 * headers both ways, including Set-Cookie, so cookies stay first-party and host-only.
 */

const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";

// Headers that must not be copied from the incoming request, or that Next.js/undici set itself.
const STRIP_REQUEST_HEADERS = new Set(["host", "connection", "content-length"]);

async function forward(request: NextRequest, params: Promise<{ path: string[] }>) {
  const { path } = await params;
  const search = request.nextUrl.search;
  // This route lives at /api/[...path], so a browser request to /api/v1/auth/login already has
  // `path` = ["v1", "auth", "login"] — don't prepend "v1" again here.
  const target = `${BACKEND_URL}/api/${path.join("/")}${search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!STRIP_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });
  // The backend rate limiter keys on the caller's IP (ARCHITECTURE.md §9) — pass the real client
  // IP through, the way Cloudflare would once a domain exists (A17).
  const forwardedFor = request.headers.get("x-forwarded-for") || "";
  if (forwardedFor) headers.set("x-forwarded-for", forwardedFor);

  const hasBody = !["GET", "HEAD"].includes(request.method);

  const backendResponse = await fetch(target, {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
    redirect: "manual",
  });

  const responseHeaders = new Headers();
  backendResponse.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (lower !== "content-encoding" && lower !== "set-cookie") responseHeaders.set(key, value);
  });
  // The login/refresh/logout responses set three separate cookies (access_token, refresh_token,
  // csrf_token). A plain forEach + Headers.set() would silently drop all but the last one, since
  // Headers.set() overwrites rather than appends — use append() with the runtime's multi-value
  // getter instead, so every Set-Cookie header actually reaches the browser.
  for (const cookie of backendResponse.headers.getSetCookie()) {
    responseHeaders.append("set-cookie", cookie);
  }

  return new NextResponse(backendResponse.body, {
    status: backendResponse.status,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(request, ctx.params);
}
export async function POST(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(request, ctx.params);
}
export async function PUT(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(request, ctx.params);
}
export async function PATCH(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(request, ctx.params);
}
export async function DELETE(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  return forward(request, ctx.params);
}
