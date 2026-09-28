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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  // FormData sets its own multipart boundary — never override it with application/json.
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  withCsrf(method, headers);

  const response = await fetch(`${API_URL}${path}`, { ...options, method, headers });
  if (response.status === 204) return undefined as T;
  if (!response.ok) throw await toApiError(response);

  const isJson = response.headers.get("content-type")?.includes("application/json");
  return (isJson ? await response.json().catch(() => null) : undefined) as T;
}

async function requestBlob(path: string, options: RequestInit = {}): Promise<{ blob: Blob; filename: string | null }> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  withCsrf(method, headers);

  const response = await fetch(`${API_URL}${path}`, { ...options, method, headers });
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
