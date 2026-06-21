import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Users, Stethoscope, CalendarClock, CreditCard,
  ShieldCheck, TrendingUp, Clock, FileText, AlertCircle, MessageSquare,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () => ({ meta: [{ title: "Dashboard — Aetheris" }] }),
  component: DashboardPage,
});

// ── Per-role stat config ────────────────────────────────────────────────────

type StatDef = {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  to?: string;
  format?: (v: number) => string;
  highlight?: (v: number) => boolean; // true → amber accent
};

const ROLE_STATS: Record<string, StatDef[]> = {
  admin: [
    { key: "total_users",        label: "Total users",          icon: Users,         to: "/patients" },
    { key: "total_patients",     label: "Patients",             icon: Users,         to: "/patients" },
    { key: "total_doctors",      label: "Doctors",              icon: Stethoscope,   to: "/doctors" },
    { key: "total_appointments", label: "Appointments",         icon: CalendarClock, to: "/appointments" },
    { key: "unpaid_invoices",    label: "Unpaid invoices",      icon: CreditCard,    to: "/billing",
      highlight: (v) => v > 0 },
    { key: "recent_audit_events",label: "Recent audit events",  icon: ShieldCheck,   to: "/audit-logs" },
  ],
  doctor: [
    { key: "total_appointments",    label: "Total appointments",    icon: CalendarClock, to: "/appointments" },
    { key: "upcoming_appointments", label: "Upcoming",              icon: Clock,         to: "/appointments",
      highlight: (v) => v > 0 },
    { key: "emr_records_authored",  label: "EMR records authored",  icon: FileText,      to: "/emr" },
  ],
  nurse: [
    { key: "total_appointments",    label: "Total appointments", icon: CalendarClock, to: "/appointments" },
    { key: "scheduled_appointments",label: "Scheduled today",    icon: Clock,         to: "/appointments",
      highlight: (v) => v > 0 },
  ],
  receptionist: [
    { key: "appointments_today", label: "Appointments today", icon: CalendarClock, to: "/appointments",
      highlight: (v) => v > 0 },
    { key: "unpaid_invoices",    label: "Unpaid invoices",    icon: CreditCard,    to: "/billing",
      highlight: (v) => v > 0 },
  ],
};

// ── Stat card ───────────────────────────────────────────────────────────────

function StatCard({
  label, value, icon: Icon, to, highlighted, loading,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  to?: string;
  highlighted?: boolean;
  loading?: boolean;
}) {
  const inner = (
    <Card className={highlighted ? "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30" : ""}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        <Icon className={`h-4 w-4 ${highlighted ? "text-amber-500" : "text-muted-foreground"}`} />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-20" />
        ) : (
          <div className={`text-3xl font-bold tracking-tight ${highlighted ? "text-amber-700 dark:text-amber-400" : ""}`}>
            {value.toLocaleString()}
          </div>
        )}
        {to && !loading && (
          <p className="mt-1 text-xs text-muted-foreground flex items-center gap-1">
            <TrendingUp className="h-3 w-3" /> View details
          </p>
        )}
      </CardContent>
    </Card>
  );

  return to ? <Link to={to} className="block">{inner}</Link> : inner;
}

// ── Quick-action links per role ──────────────────────────────────────────────

const ROLE_ACTIONS: Record<string, { label: string; to: string; icon: React.ComponentType<{ className?: string }> }[]> = {
  admin: [
    { label: "Manage patients", to: "/patients",     icon: Users },
    { label: "Manage doctors",  to: "/doctors",      icon: Stethoscope },
    { label: "View billing",    to: "/billing",      icon: CreditCard },
    { label: "Audit logs",      to: "/audit-logs",   icon: ShieldCheck },
  ],
  doctor: [
    { label: "My appointments", to: "/appointments", icon: CalendarClock },
    { label: "EMR records",     to: "/emr",          icon: FileText },
    { label: "Triage chatbot",  to: "/chatbot",      icon: MessageSquare },
  ],
  nurse: [
    { label: "Appointments",    to: "/appointments", icon: CalendarClock },
    { label: "Patients",        to: "/patients",     icon: Users },
  ],
  receptionist: [
    { label: "Appointments",    to: "/appointments", icon: CalendarClock },
    { label: "Billing",         to: "/billing",      icon: CreditCard },
    { label: "Patients",        to: "/patients",     icon: Users },
  ],
};

// ── Page ────────────────────────────────────────────────────────────────────

function DashboardPage() {
  const { user } = useAuth();
  const role = user?.role ?? "admin";

  // Prefer a real name from the doctor/patient profile if it ever surfaces
  // on the user object; fall back to the email prefix only if nothing better
  // is available — "yugimoto836" is not a great greeting.
  const displayName =
    (user as { name?: string } | null)?.name?.split(" ")[0] ||
    user?.email?.split("@")[0] ||
    "";

  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.get<Record<string, unknown>>("/dashboard/"),
  });

  const statDefs = ROLE_STATS[role] ?? [];
  const actions  = ROLE_ACTIONS[role] ?? [];

  // Backend may return a message-only object (e.g. no doctor profile linked yet)
  const message = data && typeof data["message"] === "string" ? data["message"] : null;

  return (
    <div className="space-y-8">
      <PageHeader
        title={`Welcome back${displayName ? `, ${displayName}` : ""}`}
        description={`Signed in as ${role}.`}
      />

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error instanceof ApiError ? error.message : "Failed to load dashboard data."}
        </div>
      )}

      {/* Backend message (e.g. no profile linked) */}
      {message && (
        <div className="flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {message}
        </div>
      )}

      {/* Stat cards */}
      {!message && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {isLoading
            ? Array.from({ length: statDefs.length || 3 }).map((_, i) => (
                <Card key={i}>
                  <CardHeader className="pb-2">
                    <Skeleton className="h-4 w-32" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-8 w-20" />
                  </CardContent>
                </Card>
              ))
            : statDefs.map((def) => {
                const raw = data?.[def.key];
                const value = typeof raw === "number" ? raw : 0;
                const highlighted = def.highlight ? def.highlight(value) : false;
                return (
                  <StatCard
                    key={def.key}
                    label={def.label}
                    value={value}
                    icon={def.icon}
                    to={def.to}
                    highlighted={highlighted}
                    loading={isLoading}
                  />
                );
              })}
        </div>
      )}

      {/* Quick actions */}
      {actions.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground uppercase tracking-wider">
            Quick actions
          </h2>
          <div className="flex flex-wrap gap-2">
            {actions.map((a) => (
              <Link key={a.to} to={a.to}>
                <Button variant="outline" size="sm" className="gap-2">
                  <a.icon className="h-3.5 w-3.5" />
                  {a.label}
                </Button>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
