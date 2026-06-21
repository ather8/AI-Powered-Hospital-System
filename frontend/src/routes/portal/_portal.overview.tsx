/**
 * Patient Portal — Overview / Home
 * Shows a greeting, quick stats (next appointment, outstanding balance,
 * unread notifications) and quick-action cards.
 */
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CalendarClock, CreditCard, FileText, Bell, ArrowRight, AlertCircle, Bot } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/portal/_portal/overview")({
  head: () => ({ meta: [{ title: "My Health Portal — Aetheris" }] }),
  component: PortalOverview,
});

interface PagedAppointment {
  data: Array<{ id: string; scheduled_time: string; status: string; doctor_id: string }>;
  meta: { total: number };
}
interface PagedBill {
  data: Array<{ id: string; amount: number; status: string }>;
  meta: { total: number };
}
interface NotifCount { count: number }
interface MyPatient { id: string; name: string }

function StatCard({
  title,
  value,
  sub,
  icon: Icon,
  to,
  loading,
  error,
}: {
  title: string;
  value: string | number;
  sub?: string;
  icon: React.ComponentType<{ className?: string }>;
  to: string;
  loading?: boolean;
  error?: boolean;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-7 w-24" />
        ) : error ? (
          <div className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" />
            Couldn't load
          </div>
        ) : (
          <div className="text-2xl font-bold">{value}</div>
        )}
        {sub && !loading && !error && (
          <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
        )}
        <Link to={to}>
          <Button variant="link" size="sm" className="mt-2 h-auto p-0 text-xs">
            {error ? "Try again" : "View all"} <ArrowRight className="ml-1 h-3 w-3" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

function PortalOverview() {
  const { user } = useAuth();

  const profile = useQuery({
    queryKey: ["portal-my-patient"],
    queryFn: () => api.get<MyPatient>("/patients/me"),
    retry: false,
    throwOnError: false,
  });

  const displayName =
    profile.data?.name?.split(" ")[0] ||
    user?.email?.split("@")[0] ||
    "";

  const appts = useQuery({
    queryKey: ["portal-appointments"],
    queryFn: () => api.get<PagedAppointment>("/appointments/?limit=5"),
  });

  const bills = useQuery({
    queryKey: ["portal-bills"],
    queryFn: () => api.get<PagedBill>("/billing/me?limit=20"),
  });

  const notifs = useQuery({
    queryKey: ["portal-notif-count"],
    queryFn: () => api.get<NotifCount>("/notifications/unread-count"),
  });

  const nextAppt = appts.data?.data?.find((a) => a.status === "scheduled");
  const unpaidTotal = bills.data?.data
    ?.filter((b) => b.status === "unpaid" || b.status === "partially_paid")
    .reduce((s, b) => s + b.amount, 0) ?? 0;

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">
          {greeting}{displayName ? `, ${displayName}` : ""}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Here's a summary of your health account.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Next appointment"
          value={
            nextAppt
              ? new Date(nextAppt.scheduled_time).toLocaleDateString([], {
                  month: "short",
                  day: "numeric",
                })
              : "None"
          }
          sub={
            nextAppt
              ? new Date(nextAppt.scheduled_time).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "No upcoming appointments"
          }
          icon={CalendarClock}
          to="/portal/appointments"
          loading={appts.isLoading}
          error={appts.isError}
        />
        <StatCard
          title="Total appointments"
          value={appts.data?.meta?.total ?? "—"}
          sub="lifetime"
          icon={CalendarClock}
          to="/portal/appointments"
          loading={appts.isLoading}
          error={appts.isError}
        />
        <StatCard
          title="Outstanding balance"
          value={unpaidTotal > 0 ? `$${unpaidTotal.toFixed(2)}` : "$0.00"}
          sub={unpaidTotal > 0 ? "Payment due" : "All paid up"}
          icon={CreditCard}
          to="/portal/bills"
          loading={bills.isLoading}
          error={bills.isError}
        />
        <StatCard
          title="Unread notifications"
          value={notifs.data?.count ?? "—"}
          sub=""
          icon={Bell}
          to="/portal/notifications"
          loading={notifs.isLoading}
          error={notifs.isError}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link to="/portal/appointments">
          <Card className="cursor-pointer transition-shadow hover:shadow-md">
            <CardContent className="flex items-center gap-3 pt-6">
              <CalendarClock className="h-8 w-8 text-primary" />
              <div>
                <div className="font-medium">Appointments</div>
                <div className="text-xs text-muted-foreground">Book or manage visits</div>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link to="/portal/bills">
          <Card className="cursor-pointer transition-shadow hover:shadow-md">
            <CardContent className="flex items-center gap-3 pt-6">
              <CreditCard className="h-8 w-8 text-primary" />
              <div>
                <div className="font-medium">Bills & Payments</div>
                <div className="text-xs text-muted-foreground">View invoices, pay online</div>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link to="/portal/records">
          <Card className="cursor-pointer transition-shadow hover:shadow-md">
            <CardContent className="flex items-center gap-3 pt-6">
              <FileText className="h-8 w-8 text-primary" />
              <div>
                <div className="font-medium">My Records</div>
                <div className="text-xs text-muted-foreground">View your medical history</div>
              </div>
            </CardContent>
          </Card>
        </Link>
        <Link to="/portal/chatbot">
          <Card className="cursor-pointer transition-shadow hover:shadow-md">
            <CardContent className="flex items-center gap-3 pt-6">
              <Bot className="h-8 w-8 text-primary" />
              <div>
                <div className="font-medium">Symptom Checker</div>
                <div className="text-xs text-muted-foreground">AI-powered triage assistant</div>
              </div>
            </CardContent>
          </Card>
        </Link>
      </div>

      {unpaidTotal > 0 && (
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/20">
          <CardContent className="flex items-center justify-between pt-4 pb-4">
            <div className="flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-amber-600" />
              <span className="text-sm font-medium text-amber-800 dark:text-amber-300">
                You have an outstanding balance of{" "}
                <strong>${unpaidTotal.toFixed(2)}</strong>
              </span>
            </div>
            <Link to="/portal/bills">
              <Button size="sm" variant="outline" className="border-amber-400">
                Pay now
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
