import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// Shared poll interval so the sidebar badge and the notifications page
// agree on cadence. Notifications aren't latency-critical, so a light
// 30s poll (rather than websockets) is enough to make "new notification"
// show up without a manual refresh.
export const NOTIFICATIONS_POLL_INTERVAL_MS = 30_000;

interface UnreadCount {
  count: number;
}

/** Powers the sidebar badge. Hits a dedicated lightweight endpoint instead
 * of fetching the full notification list just to count unread ones. */
export function useUnreadNotificationCount() {
  return useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => api.get<UnreadCount>("/notifications/unread-count"),
    refetchInterval: NOTIFICATIONS_POLL_INTERVAL_MS,
    staleTime: 10_000,
  });
}
