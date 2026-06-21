/**
 * Patient Portal layout — a slimmer shell than the staff /_authenticated
 * layout. Patients land here after login when they have the "patient" role.
 * Staff can still visit /portal routes (e.g. to demo), but the nav is
 * intentionally patient-facing: no admin links, friendly language.
 *
 * The route file is named _portal.tsx so TanStack Router treats it as a
 * pathless layout route that wraps all child routes whose filenames begin
 * with "_portal.". Auth guard mirrors _authenticated.tsx.
 */
import { createFileRoute, Outlet, Link, redirect } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Heart, CalendarClock, CreditCard, FileText, Bell, LogOut, UserPlus, Bot } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { api, getToken } from "@/lib/api";

export const Route = createFileRoute("/portal/_portal")({
  beforeLoad: ({ location }) => {
    if (typeof window !== "undefined" && !getToken()) {
      throw redirect({ to: "/login", search: { redirect: location.href } });
    }
  },
  component: PortalLayout,
});

const NAV_ITEMS = [
  { to: "/portal/overview", label: "Overview", mobileLabel: "Home", icon: Heart },
  { to: "/portal/appointments", label: "Appointments", mobileLabel: "Appts", icon: CalendarClock },
  { to: "/portal/bills", label: "Bills", mobileLabel: "Bills", icon: CreditCard },
  { to: "/portal/records", label: "My Records", mobileLabel: "Records", icon: FileText },
  { to: "/portal/notifications", label: "Notifications", mobileLabel: "Alerts", icon: Bell },
  { to: "/portal/chatbot", label: "Symptoms", mobileLabel: "Symptoms", icon: Bot },
];

function PortalLayout() {
  const { user, logout } = useAuth();

  // Surfaced on every portal page (not just appointments) so a patient who
  // lands on, say, /portal/overview or /portal/bills right after signup
  // still finds their way to profile creation instead of discovering the
  // gap only when an action fails.
  const myProfileQ = useQuery({
    queryKey: ["portal-my-patient"],
    queryFn: () => api.get<{ id: string }>("/patients/me"),
    retry: false,
    throwOnError: false,
  });
  const showProfileBanner = myProfileQ.isFetched && !myProfileQ.data;

  return (
    <div className="min-h-screen bg-background">
      {/* Top nav */}
      <header className="sticky top-0 z-20 border-b bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
          <Link to="/portal/overview" className="flex items-center gap-2 font-semibold">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Heart className="h-4 w-4" />
            </div>
            <span className="text-sm">Aetheris Health</span>
          </Link>

          <nav className="hidden flex-1 justify-center gap-1 sm:flex">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground [&.active]:bg-muted [&.active]:text-foreground [&.active]:font-medium"
              >
                <item.icon className="h-3.5 w-3.5" />
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-xs text-muted-foreground sm:block">
              {user?.email}
            </span>
            <Button variant="ghost" size="sm" onClick={logout} className="gap-1.5">
              <LogOut className="h-3.5 w-3.5" />
              Sign out
            </Button>
          </div>
        </div>

        {/* Mobile nav */}
        <div className="flex gap-1 overflow-x-auto px-4 pb-2 sm:hidden">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="flex shrink-0 items-center gap-1 rounded-md px-2.5 py-1 text-xs text-muted-foreground [&.active]:bg-muted [&.active]:text-foreground [&.active]:font-medium"
            >
              <item.icon className="h-3 w-3" />
              {item.mobileLabel}
            </Link>
          ))}
        </div>
      </header>

      {showProfileBanner && (
        <div className="border-b bg-amber-50 dark:bg-amber-950/20">
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-2.5">
            <div className="flex items-center gap-2 text-sm text-amber-800 dark:text-amber-300">
              <UserPlus className="h-4 w-4 shrink-0" />
              <span>Finish setting up your account to book appointments and view your records.</span>
            </div>
            <Link to="/portal/create-profile">
              <Button size="sm" variant="outline" className="border-amber-400">
                Create my profile
              </Button>
            </Link>
          </div>
        </div>
      )}

      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
