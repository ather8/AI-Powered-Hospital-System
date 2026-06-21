import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { requireRole } from "@/lib/route-guard";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const Route = createFileRoute("/_authenticated/analytics")({
  beforeLoad: () => requireRole("/analytics"),
  head: () => ({ meta: [{ title: "Analytics — Aetheris" }] }),
  component: Page,
});

function Page() {
  const q = useQuery({ queryKey: ["analytics"], queryFn: () => api.get<Record<string, unknown>>("/analytics/") });
  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Admin-only platform analytics." />
      {q.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {q.error && <p className="text-sm text-destructive">{(q.error as Error).message}</p>}
      {q.data && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(q.data).map(([k, v]) => (
            <Card key={k}>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{k.replace(/_/g, " ")}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-semibold">
                  {typeof v === "object" ? <pre className="max-h-40 overflow-auto text-xs">{JSON.stringify(v, null, 2)}</pre> : String(v)}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
