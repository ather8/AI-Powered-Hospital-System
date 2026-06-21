import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api, API_BASE, getToken } from "@/lib/api";
import { requireRole } from "@/lib/route-guard";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { usePagination } from "@/hooks/use-pagination";

interface AuditLog {
  id: string;
  user_id: string;
  action: string;
  resource: string;
  resource_id: string;
  timestamp: string;
  details: string;
}

interface PagedAuditLogs {
  data: AuditLog[];
  meta: { total: number; skip: number; limit: number; has_next: boolean; has_prev: boolean };
}

export const Route = createFileRoute("/_authenticated/audit-logs")({
  beforeLoad: () => requireRole("/audit-logs"),
  head: () => ({ meta: [{ title: "Audit Logs — Aetheris" }] }),
  component: Page,
});

function Page() {
  const page = usePagination(20);

  const q = useQuery({
    queryKey: ["audit-logs", page.skip, page.limit],
    queryFn: () => api.get<PagedAuditLogs>("/audit-logs/", { skip: page.skip, limit: page.limit }),
  });

  async function exportCsv() {
    const token = getToken();
    const res = await fetch(`${API_BASE}/export/audit/csv`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "audit_logs.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  const paged = q.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Logs"
        description={
          paged
            ? `Admin-only activity trail — ${paged.meta.total} total entries`
            : "Admin-only activity trail."
        }
        actions={<Button variant="outline" onClick={exportCsv}>Export CSV</Button>}
      />
      {q.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {q.error && <p className="text-sm text-destructive">{(q.error as Error).message}</p>}
      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30 text-left text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3">When</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Resource</th>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Details</th>
              </tr>
            </thead>
            <tbody>
              {paged?.data.map((l) => (
                <tr key={l.id} className="border-b last:border-0">
                  <td className="px-4 py-2 text-xs text-muted-foreground">
                    {l.timestamp ? new Date(l.timestamp).toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-2 font-medium">{l.action}</td>
                  <td className="px-4 py-2">{l.resource}</td>
                  <td className="px-4 py-2 font-mono text-xs">{l.user_id?.slice(0, 8)}…</td>
                  <td className="px-4 py-2 text-muted-foreground">{l.details}</td>
                </tr>
              ))}
              {paged?.data.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-sm text-muted-foreground">
                    No audit log entries yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {paged && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={page.prev}
            disabled={!paged.meta.has_prev || q.isFetching}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            {paged.meta.skip + 1}–{Math.min(paged.meta.skip + paged.meta.limit, paged.meta.total)} of {paged.meta.total}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={page.next}
            disabled={!paged.meta.has_next || q.isFetching}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
