// Lightweight API client for the FastAPI hospital backend.
// Base URL is configured via VITE_API_BASE_URL.

const RAW_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const API_BASE = RAW_BASE.replace(/\/$/, "");
const TOKEN_KEY = "hospital_token";

// Mock-only: backend/app/routes/stripe_mock.py requires this header on
// POST /billing/stripe/webhook since that endpoint has no JWT to check
// (real Stripe calls it server-to-server, not from a logged-in browser).
// See the comment in frontend/.env for why this is fine for the mock but
// wouldn't be how a real webhook secret is handled.
export const STRIPE_WEBHOOK_SECRET = import.meta.env.VITE_STRIPE_WEBHOOK_SECRET || "";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
  isHandlingUnauthorized = false;
}

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

// Fired when an *authenticated* request comes back 401 — i.e. the token we
// sent was rejected (expired/invalidated), not when an anonymous request
// like /auth/login fails because of a wrong password. AuthProvider installs
// this once, at the app root, so any query/mutation anywhere can trigger a
// clean logout + redirect instead of the page just sitting there broken.
let unauthorizedHandler: (() => void) | null = null;
let isHandlingUnauthorized = false;

export function setUnauthorizedHandler(fn: (() => void) | null) {
  unauthorizedHandler = fn;
}

type Options = {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  formData?: FormData;
  headers?: Record<string, string>;
  raw?: boolean; // return Response (e.g. for blob downloads)
};

export async function apiFetch<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const { method = "GET", body, query, formData, headers = {}, raw } = opts;
  const url = new URL(API_BASE + path);
  if (query) {
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    });
  }

  const token = getToken();
  const reqHeaders: Record<string, string> = { ...headers };
  if (token) reqHeaders["Authorization"] = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (formData) {
    payload = formData;
  } else if (body !== undefined) {
    reqHeaders["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(url.toString(), { method, headers: reqHeaders, body: payload });
  if (raw) return res as unknown as T;

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    // Only treat this as "your session died" if we actually sent a token.
    // A 401 with no token attached is a normal failed-login/anonymous-route
    // response and must not force a logout/redirect.
    if (res.status === 401 && token && !isHandlingUnauthorized) {
      isHandlingUnauthorized = true;
      unauthorizedHandler?.();
    }
    const msg =
      (data && typeof data === "object" && "detail" in (data as Record<string, unknown>)
        ? String((data as { detail: unknown }).detail)
        : res.statusText) || "Request failed";
    throw new ApiError(res.status, msg, data);
  }
  return data as T;
}

// Convenience helpers
export const api = {
  get: <T>(p: string, query?: Options["query"]) => apiFetch<T>(p, { query }),
  post: <T>(p: string, body?: unknown) => apiFetch<T>(p, { method: "POST", body }),
  put: <T>(p: string, body?: unknown) => apiFetch<T>(p, { method: "PUT", body }),
  patch: <T>(p: string, body?: unknown) => apiFetch<T>(p, { method: "PATCH", body }),
  del: <T>(p: string) => apiFetch<T>(p, { method: "DELETE" }),
  upload: <T>(p: string, formData: FormData) => apiFetch<T>(p, { method: "POST", formData }),
};
