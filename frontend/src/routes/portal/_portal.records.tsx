/**
 * Patient Portal — My Records
 * Shows the patient's own EMR entries.
 */
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText } from "lucide-react";

export const Route = createFileRoute("/portal/_portal/records")({
  head: () => ({ meta: [{ title: "My Records — Aetheris" }] }),
  component: PortalRecords,
});

interface EmrRecord {
  id: string;
  patient_id: string;
  diagnosis: string | null;
  notes: string | null;
  treatment: string | null;
  created_at?: string;
}

interface PagedEmr {
  data: EmrRecord[];
  meta: { total: number };
}

function PortalRecords() {
  const emrQ = useQuery({
    queryKey: ["portal-emr"],
    // Router is mounted at /emrs (plural, see app/routes/emr.py), and /me
    // is the dedicated patient-scoped route — GET /emrs/{patient_id} would
    // require knowing the patient's own UUID, which the portal doesn't have.
    queryFn: () => api.get<PagedEmr | EmrRecord[]>("/emrs/me"),
  });

  // The EMR endpoint may return a paged envelope or a bare array depending
  // on the server version — handle both.
  const records: EmrRecord[] = Array.isArray(emrQ.data)
    ? emrQ.data
    : (emrQ.data as PagedEmr)?.data ?? [];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">My Medical Records</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your clinical notes and diagnoses from visits.
        </p>
      </div>

      {emrQ.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      )}

      {emrQ.isError && (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            Could not load your records. Please try again later.
          </CardContent>
        </Card>
      )}

      {!emrQ.isLoading && records.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            <FileText className="mx-auto mb-2 h-8 w-8 opacity-30" />
            No medical records on file yet.
          </CardContent>
        </Card>
      )}

      <div className="space-y-4">
        {records.map((r) => (
          <Card key={r.id}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  {r.diagnosis ?? "Visit record"}
                </CardTitle>
                {r.created_at && (
                  <span className="text-xs text-muted-foreground">
                    {new Date(r.created_at).toLocaleDateString([], {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {r.notes && (
                <div>
                  <span className="font-medium">Notes: </span>
                  <span className="text-muted-foreground">{r.notes}</span>
                </div>
              )}
              {r.treatment && (
                <div>
                  <span className="font-medium">Treatment: </span>
                  <span className="text-muted-foreground">{r.treatment}</span>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <p className="text-xs text-muted-foreground">
        If you believe there is an error in your records, please contact
        your care team.
      </p>
    </div>
  );
}
