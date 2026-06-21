/**
 * /auth/callback
 *
 * Landing page after Google OAuth. The backend redirects here with the
 * JWT in the URL fragment:  /auth/callback#token=eyJ...
 *
 * Reading from the fragment (not the query string) means the token never
 * appears in server logs or the browser's history in plain sight.
 *
 * This page reads the token, hands it to AuthContext, then immediately
 * navigates to /portal/overview (patients) or /dashboard (everyone else),
 * or /login on error.
 */
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { userFromToken } from "@/lib/auth";

export const Route = createFileRoute("/auth/callback")({
  head: () => ({ meta: [{ title: "Signing in… — Aetheris" }] }),
  component: GoogleCallbackPage,
});

function GoogleCallbackPage() {
  const { handleGoogleCallback } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // Parse fragment: #token=eyJ...
    const fragment = window.location.hash.slice(1); // remove leading #
    const params = new URLSearchParams(fragment);
    const token = params.get("token");

    if (token) {
      handleGoogleCallback(token);
      toast.success("Signed in with Google");
      // Patients go to the patient portal; all other roles go to the staff
      // dashboard — same rule as the email/password login path.
      const u = userFromToken(token);
      navigate({ to: u?.role === "patient" ? "/portal/overview" : "/dashboard", replace: true });
    } else {
      toast.error("Google sign-in failed — no token received");
      navigate({ to: "/login", replace: true });
    }
  }, [handleGoogleCallback, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <p className="text-sm text-muted-foreground">Completing sign-in…</p>
    </div>
  );
}
