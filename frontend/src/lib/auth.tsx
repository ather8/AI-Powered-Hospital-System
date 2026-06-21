import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { api, API_BASE, getToken, setToken, setUnauthorizedHandler } from "./api";

export type Role = "admin" | "doctor" | "nurse" | "receptionist" | "patient" | string;

export interface AuthUser {
  id: string;
  role: Role;
  email?: string;
}

interface JwtPayload {
  sub?: string;
  role?: string;
  email?: string;
  exp?: number;
}

function decodeJwt(token: string): JwtPayload | null {
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, role: Role) => Promise<void>;
  loginWithGoogle: () => void;
  handleGoogleCallback: (token: string) => void;
  logout: () => void;
  hasRole: (r: Role | Role[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function userFromToken(token: string | null): AuthUser | null {
  if (!token) return null;
  const p = decodeJwt(token);
  if (!p?.sub) return null;
  if (p.exp && p.exp * 1000 < Date.now()) return null;
  return { id: p.sub, role: (p.role as Role) ?? "patient", email: p.email };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setTokState] = useState<string | null>(() => getToken());
  const [user, setUser] = useState<AuthUser | null>(() => userFromToken(getToken()));

  useEffect(() => {
    setUser(userFromToken(token));
  }, [token]);

  // React Query's cache is keyed by query (e.g. ["notifications"]), not by
  // user. Without clearing it here, switching accounts in the same browser
  // tab (logout -> login as someone else, no full page reload) could
  // briefly render the previous user's cached notifications/patients/etc.
  // before the refetch resolves — a real cross-user data leak, not just a
  // cosmetic flash. Clear on every identity change: in (new token replaces
  // old/none) and out (token removed).
  const _setAuth = useCallback((t: string) => {
    queryClient.clear();
    setToken(t);
    setTokState(t);
  }, [queryClient]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post<{ access_token: string }>("/auth/login", { email, password });
    _setAuth(res.access_token);
  }, [_setAuth]);

  const register = useCallback(async (email: string, password: string, role: Role) => {
    const res = await api.post<{ access_token: string }>("/auth/register", { email, password, role });
    _setAuth(res.access_token);
  }, [_setAuth]);

  /** Redirect the browser to the backend Google OAuth entry point. */
  const loginWithGoogle = useCallback(() => {
    window.location.href = `${API_BASE}/auth/google/`;
  }, []);

  /**
   * Called by the /auth/callback route after Google redirects back.
   * Receives the JWT that the backend embedded in the URL fragment.
   */
  const handleGoogleCallback = useCallback((t: string) => {
    _setAuth(t);
  }, [_setAuth]);

  // Used when the *server* ends the session (expired/invalid token), as
  // opposed to the user clicking "Log out". Skips the /auth/logout call —
  // the token is already rejected, so that request would just 401 again —
  // and bounces to /login with an explanation instead of leaving a broken
  // page on screen.
  const navigate = useNavigate();

  const logout = useCallback(() => {
    api.post("/auth/logout").catch(() => {});
    setToken(null);
    setTokState(null);
    queryClient.clear();
    navigate({ to: "/" });
  }, [queryClient, navigate]);

  const forceLogout = useCallback(() => {
    setToken(null);
    setTokState(null);
    queryClient.clear();
    toast.error("Your session has expired. Please log in again.");
    navigate({ to: "/login" });
  }, [queryClient, navigate]);

  useEffect(() => {
    setUnauthorizedHandler(forceLogout);
    return () => setUnauthorizedHandler(null);
  }, [forceLogout]);

  const hasRole = useCallback(
    (r: Role | Role[]) => {
      if (!user) return false;
      const list = Array.isArray(r) ? r : [r];
      return list.includes(user.role);
    },
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, isAuthenticated: !!user, login, register, loginWithGoogle, handleGoogleCallback, logout, hasRole }),
    [user, token, login, register, loginWithGoogle, handleGoogleCallback, logout, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
