/**
 * Patient Portal — Notifications
 * Re-surfaces the existing notifications endpoint in the patient-friendly portal shell.
 */
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Bell } from "lucide-react";

export const Route = createFileRoute("/portal/_portal/notifications")({
  head: () => ({ meta: [{ title: "Notifications — Aetheris" }] }),
  component: PortalNotifications,
});

interface Notification {
  id: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

interface PagedNotif {
  data: Notification[];
  meta: { total: number };
}

function PortalNotifications() {
  const qc = useQueryClient();

  const notifsQ = useQuery({
    queryKey: ["portal-notifications"],
    queryFn: () => api.get<PagedNotif | Notification[]>("/notifications/"),
  });

  const markRead = useMutation({
    // Backend route is PATCH /notifications/{id}/read (see
    // app/routes/notifications.py) — PUT here would 405. The staff-side
    // notifications page (_authenticated.notifications.tsx) already uses
    // PATCH; this brings the portal in line with it.
    mutationFn: (id: string) => api.patch(`/notifications/${id}/read`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portal-notifications"] });
      qc.invalidateQueries({ queryKey: ["notification-unread-count"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed"),
  });

  const notifs: Notification[] = Array.isArray(notifsQ.data)
    ? notifsQ.data
    : (notifsQ.data as PagedNotif)?.data ?? [];

  const unread = notifs.filter((n) => !n.is_read);
  const read = notifs.filter((n) => n.is_read);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Notifications</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Updates from your care team.
        </p>
      </div>

      {notifsQ.isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      )}

      {!notifsQ.isLoading && notifs.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            <Bell className="mx-auto mb-2 h-8 w-8 opacity-30" />
            No notifications yet.
          </CardContent>
        </Card>
      )}

      {unread.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Unread
          </h2>
          {unread.map((n) => (
            <Card key={n.id} className="border-primary/30 bg-primary/5">
              <CardContent className="flex items-start justify-between gap-3 py-3">
                <div>
                  <p className="text-sm font-medium">{n.message}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(n.created_at).toLocaleString()}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={markRead.isPending}
                  onClick={() => markRead.mutate(n.id)}
                >
                  Mark read
                </Button>
              </CardContent>
            </Card>
          ))}
        </section>
      )}

      {read.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Earlier
          </h2>
          {read.map((n) => (
            <Card key={n.id} className="opacity-60">
              <CardContent className="py-3">
                <p className="text-sm">{n.message}</p>
                <p className="text-xs text-muted-foreground">
                  {new Date(n.created_at).toLocaleString()}
                </p>
              </CardContent>
            </Card>
          ))}
        </section>
      )}
    </div>
  );
}
