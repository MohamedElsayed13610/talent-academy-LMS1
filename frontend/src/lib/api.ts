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
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

function withCsrf(method: string, headers: Headers): Headers {
  if (!SAFE_METHODS.has(method)) {
    const csrf = readCookie("csrf_token");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  return headers;
}

async function toApiError(response: Response): Promise<ApiError> {
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await response.json().catch(() => null) : null;
  const err = payload?.error;
  return new ApiError(response.status, err?.code || "UNKNOWN_ERROR", err?.message || "حدث خطأ غير متوقع", err?.details || {});
}

// ------------------------------------------------------------------------- session refresh ----
//
// The access-token cookie lives ACCESS_TOKEN_EXPIRE_MINUTES (15 min); the refresh-token cookie
// (Path=/api/v1/auth) lives much longer. On a 401 we rotate once via POST /auth/refresh and retry.
// Single-flight: every request that 401s while a refresh is in flight awaits that same refresh.

type RefreshOutcome = "ok" | "rejected" | "unavailable";

// Endpoints whose 401 means "wrong credentials / no session", not "access token expired".
const NO_REFRESH_PATHS = new Set(["/auth/login", "/auth/refresh", "/auth/logout"]);

let refreshInFlight: Promise<RefreshOutcome> | null = null;
let lastRefreshAt = 0;

function refreshSession(): Promise<RefreshOutcome> {
  if (!refreshInFlight) {
    refreshInFlight = (async (): Promise<RefreshOutcome> => {
      try {
        const response = await fetch(`${API_URL}/auth/refresh`, { method: "POST", headers: withCsrf("POST", new Headers()) });
        if (response.ok) {
          lastRefreshAt = Date.now();
          return "ok";
        }
        // 401/403: the refresh token itself is gone, expired, or revoked — the session is over.
        // Anything else (5xx, 429) is transient and must not log anyone out mid-exam.
        return response.status === 401 || response.status === 403 ? "rejected" : "unavailable";
      } catch {
        return "unavailable"; // offline / network error
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

function redirectToLogin() {
  if (typeof window === "undefined" || window.location.pathname === "/login") return;
  // A hard navigation on purpose: this runs outside React (no router here), and a full reload is
  // what drops the ended session's cached queries and in-memory state.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign("/login");
}

// Builds headers per attempt, so a retry picks up the csrf_token cookie the refresh just rotated.
function send(path: string, options: RequestInit, method: string): Promise<Response> {
  const headers = new Headers(options.headers);
  // FormData sets its own multipart boundary — never override it with application/json.
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  withCsrf(method, headers);
  return fetch(`${API_URL}${path}`, { ...options, method, headers });
}

async function fetchWithRefresh(path: string, options: RequestInit): Promise<Response> {
  const method = (options.method || "GET").toUpperCase();
  const sentAt = Date.now();
  const response = await send(path, options, method);
  if (response.status !== 401 || NO_REFRESH_PATHS.has(path)) return response;

  // Sent with the old cookie before a refresh that has since completed → just retry, don't
  // rotate again.
  const outcome = sentAt < lastRefreshAt ? "ok" : await refreshSession();
  if (outcome === "ok") return send(path, options, method);
  if (outcome === "rejected") redirectToLogin();
  return response;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetchWithRefresh(path, options);
  if (response.status === 204) return undefined as T;
  if (!response.ok) throw await toApiError(response);

  const isJson = response.headers.get("content-type")?.includes("application/json");
  return (isJson ? await response.json().catch(() => null) : undefined) as T;
}

async function requestBlob(path: string, options: RequestInit = {}): Promise<{ blob: Blob; filename: string | null }> {
  const response = await fetchWithRefresh(path, options);
  if (!response.ok) throw await toApiError(response);
  const disposition = response.headers.get("content-disposition");
  const match = disposition?.match(/filename="?([^"]+)"?/);
  return { blob: await response.blob(), filename: match?.[1] || null };
}

/** Triggers a browser "save file" for a blob response — used for every .xlsx download. */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  postForm: <T,>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
  put: <T,>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T,>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
  delete: <T,>(path: string) => request<T>(path, { method: "DELETE" }),
  getBlob: (path: string) => requestBlob(path),
  postBlob: (path: string, body?: unknown) => requestBlob(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
};
