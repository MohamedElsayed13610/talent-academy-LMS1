"use client";

/**
 * Backend client. Same-origin only — the browser only ever talks to /api/v1/* on this origin,
 * which the api/[...path] route handler proxies to the backend over Railway's private network
 * (docs/ARCHITECTURE.md §1). Cookies are sent automatically (credentials: "same-origin" is the
 * default for same-origin fetches); the CSRF token is read from the non-HttpOnly cookie and
 * echoed back as a header on unsafe methods (core/csrf.py double-submit check).
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!SAFE_METHODS.has(method)) {
    const csrf = readCookie("csrf_token");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const response = await fetch(`${API_URL}${path}`, { ...options, method, headers });

  if (response.status === 204) return undefined as T;

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    const err = payload?.error;
    throw new ApiError(
      response.status,
      err?.code || "UNKNOWN_ERROR",
      err?.message || "حدث خطأ غير متوقع",
      err?.details || {},
    );
  }
  return payload as T;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T,>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T,>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T,>(path: string) => request<T>(path, { method: "DELETE" }),
};
