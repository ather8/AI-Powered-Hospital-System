import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { CheckCheck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { NOTIFICATIONS_POLL_INTERVAL_MS } from "@/hooks/use-notifications";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

// Backend Notification model fields: id, user_id, message, created_at, read, scheduled_for
interface Notif {
  id: string;
  message: string;
  created_at: string;
  read: boolean;
  scheduled_for: string | null;
}

interface Recipient {
  id: number;
  email: string;
  role: string;
}

export const Route = createFileRoute("/_authenticated/notifications")({
  head: () => ({ meta: [{ title: "Notifications — Aetheris" }] }),
  component: Page,
});

function ComposeNotification() {
  const qc = useQueryClient();
  const recipients = useQuery({
    queryKey: ["notifications", "recipients"],
    queryFn: () => api.get<Recipient[]>("/notifications/recipients"),
  });
  const [form, setForm] = useState({ user_id: "", message: "", scheduled_for: "" });

  const send = useMutation({
    mutationFn: () =>
      api.post("/notifications/", {
        user_id: Number(form.user_id),
        message: form.message,
        scheduled_for: form.scheduled_for ? new Date(form.scheduled_for).toISOString() : null,
      }),
    onSuccess: () => {
      toast.success("Notification sent");
      setForm({ user_id: "", message: "", scheduled_for: "" });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to send"),
  });

  return (
    <Card>
      <CardHeader><CardTitle>Send notification</CardTitle></CardHeader>
      <CardContent>
        <form
          onSubmit={(e) => { e.preventDefault(); send.mutate(); }}
          className="space-y-3"
        >
          <div>
            <Label>Recipient</Label>
            <Select value={form.user_id} onValueChange={(v) => setForm({ ...form, user_id: v })}>
              <SelectTrigger className="mt-1.5"><SelectValue placeholder="Choose a user…" /></SelectTrigger>
              <SelectContent>
                {recipients.data?.map((u) => (
                  <SelectItem key={u.id} value={String(u.id)}>
                    {u.email} <span className="text-muted-foreground">({u.role})</span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Message</Label>
            <Textarea
              required
              maxLength={500}
              rows={3}
              value={form.message}
              onChange={(e) => setForm({ ...form, message: e.target.value })}
              className="mt-1.5"
            />
          </div>
          <div>
            <Label>Schedule for later (optional)</Label>
            <Input
              type="datetime-local"
              value={form.scheduled_for}
              onChange={(e) => setForm({ ...form, scheduled_for: e.target.value })}
              className="mt-1.5"
            />
          </div>
          <Button type="submit" disabled={send.isPending || !form.user_id || !form.message}>
            {send.isPending ? "Sending…" : "Send notification"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function Page() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<Notif[]>("/notifications/"),
    // Light polling so a new notification shows up without the user having
    // to navigate away and back. refetchOnWindowFocus (react-query default)
    // already covers the "tab was backgrounded" case.
    refetchInterval: NOTIFICATIONS_POLL_INTERVAL_MS,
  });
  const canSend = hasRole(["admin", "receptionist"]);
  const unreadCount = q.data?.filter((n) => !n.read).length ?? 0;

  const markRead = useMutation({
    mutationFn: (id: string) => api.patch(`/notifications/${id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't mark as read"),
  });

  const markAllRead = useMutation({
    mutationFn: () => api.post("/notifications/read-all"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("All notifications marked as read");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't mark all as read"),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader title="Notifications" description="Your messages from the platform." />
        {unreadCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => markAllRead.mutate()}
            disabled={markAllRead.isPending}
            className="shrink-0"
          >
            <CheckCheck className="mr-1.5 size-4" />
            Mark all as read
          </Button>
        )}
      </div>
      <div className={canSend ? "grid gap-6 lg:grid-cols-3" : ""}>
        <div className={canSend ? "lg:col-span-2 space-y-2" : "space-y-2"}>
          {q.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {q.error && <p className="text-sm text-destructive">{(q.error as Error).message}</p>}
          {q.data?.length === 0 && <p className="text-sm text-muted-foreground">You have no notifications.</p>}
          {q.data?.map((n) => (
            <Card
              key={n.id}
              role={n.read ? undefined : "button"}
              tabIndex={n.read ? undefined : 0}
              onClick={() => !n.read && markRead.mutate(n.id)}
              onKeyDown={(e) => {
                if (!n.read && (e.key === "Enter" || e.key === " ")) markRead.mutate(n.id);
              }}
              className={cn(n.read ? "opacity-60" : "cursor-pointer transition-colors hover:bg-accent/50")}
            >
              <CardContent className="flex items-start justify-between py-3">
                <div>
                  <div className="text-sm">{n.message}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{new Date(n.created_at).toLocaleString()}</div>
                  {n.scheduled_for && (
                    <div className="mt-0.5 text-xs text-muted-foreground">
                      Scheduled: {new Date(n.scheduled_for).toLocaleString()}
                    </div>
                  )}
                </div>
                {!n.read && (
                  <Badge variant="default" className="ml-4 shrink-0">
                    New
                  </Badge>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
        {canSend && <ComposeNotification />}
      </div>
    </div>
  );
}
