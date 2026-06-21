// Single source of truth for which roles can access which authenticated
// routes. AppSidebar (components/app-sidebar.tsx) uses this same map to
// decide which links to show, and each gated route's `beforeLoad` uses
// `requireRole` below to actually enforce it.
//
// Previously the sidebar's per-item `roles` list was the ONLY gate: a
// route with no link shown still rendered its full page shell (and fired
// its data queries) for any authenticated user who typed the URL directly,
// relying on the backend's 403s + error toasts to fail the page after the
// fact. The backend was never the security hole — but the UX was a page
// flashing in before being yanked away, and it's a class of bug ("gate
// forgotten on one specific page") that recurs because the sidebar config
// and the route's own access rules lived in two unrelated places. Routes
// not listed here have no role restriction (any authenticated user may
// view them) — keep this in sync with components/app-sidebar.tsx.
import { redirect } from "@tanstack/react-router";
import { getToken } from "./api";
import { userFromToken, type Role } from "./auth";

export const ROUTE_ROLES: Record<string, Role[]> = {
  "/search": ["doctor", "nurse", "admin", "receptionist"],
  "/emr": ["doctor", "nurse", "admin", "patient"],
  "/billing": ["admin", "receptionist", "patient"],
  "/ai/clinical-search": ["doctor", "nurse"],
  "/ai/summary": ["doctor", "nurse", "admin"],
  "/ai/notes": ["doctor", "nurse"],
  "/ocr": ["doctor", "nurse", "admin"],
  "/analytics": ["admin"],
  "/audit-logs": ["admin"],
};

/**
 * Use inside a route's `beforeLoad`. Reads the JWT directly from storage
 * (beforeLoad runs outside React, so hooks like useAuth aren't available —
 * this mirrors how `_authenticated.tsx` already checks `getToken()`
 * directly for the logged-in/logged-out gate). Unauthorized visitors are
 * redirected to `/dashboard` before the page component (and its data
 * queries) ever mounts, instead of rendering the page and letting 403
 * toasts fire after the fact.
 */
export function requireRole(path: keyof typeof ROUTE_ROLES) {
  const allowed = ROUTE_ROLES[path];
  if (typeof window === "undefined") return; // SSR pass: client beforeLoad re-runs with storage available
  const user = userFromToken(getToken());
  if (!user || !allowed.includes(user.role)) {
    throw redirect({ to: "/dashboard" });
  }
}
