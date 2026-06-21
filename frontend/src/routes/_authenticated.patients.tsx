import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/lib/auth";
import { usePagination } from "@/hooks/use-pagination";

interface Patient {
  id: string;
  name: string;
  dob: string | null;
  phone: string | null;
  address: string | null;
}

interface PagedPatients {
  data: Patient[];
  meta: { total: number; skip: number; limit: number; has_next: boolean; has_prev: boolean };
}

export const Route = createFileRoute("/_authenticated/patients")({
  head: () => ({ meta: [{ title: "Patients — Aetheris" }] }),
  component: PatientsPage,
});

function PatientDetails({ patient }: { patient: Patient }) {
  return (
    <div className="mt-4 space-y-1 rounded-md border bg-muted/40 p-4 text-sm">
      <div><span className="text-muted-foreground">Name:</span> {patient.name}</div>
      <div><span className="text-muted-foreground">DOB:</span> {patient.dob ?? "—"}</div>
      <div><span className="text-muted-foreground">Phone:</span> {patient.phone ?? "—"}</div>
      <div><span className="text-muted-foreground">Address:</span> {patient.address ?? "—"}</div>
      <div className="pt-2 font-mono text-xs text-muted-foreground">{patient.id}</div>
    </div>
  );
}

function PatientsPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const [lookupId, setLookupId] = useState("");
  const [found, setFound] = useState<Patient | null>(null);
  const [form, setForm] = useState({ name: "", dob: "", phone: "", address: "" });
  const page = usePagination(20);

  // Paginated list for staff roles
  const listQuery = useQuery({
    queryKey: ["patients", page.skip, page.limit],
    queryFn: () => api.get<PagedPatients>("/patients/", { skip: page.skip, limit: page.limit }),
    enabled: hasRole(["admin", "doctor", "nurse", "receptionist"]),
  });

  const create = useMutation({
    mutationFn: () =>
      api.post<Patient>("/patients/", {
        name: form.name,
        dob: form.dob || null,
        phone: form.phone || null,
        address: form.address || null,
      }),
    onSuccess: (p) => {
      toast.success("Patient profile created");
      setFound(p);
      setForm({ name: "", dob: "", phone: "", address: "" });
      qc.invalidateQueries({ queryKey: ["patients"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed"),
  });

  const lookup = useQuery({
    queryKey: ["patient", lookupId],
    queryFn: () => api.get<Patient>(`/patients/${lookupId}`),
    enabled: false,
  });

  async function onLookup(e: React.FormEvent) {
    e.preventDefault();
    if (!lookupId) return;
    const res = await lookup.refetch();
    if (res.error) toast.error(res.error instanceof ApiError ? res.error.message : "Not found");
    else if (res.data) setFound(res.data);
  }

  const paged = listQuery.data;

  return (
    <div className="space-y-6">
      <PageHeader title="Patients" description="Patient records. RBAC enforced — patients self-manage, clinicians see the full list." />

      <div className="grid gap-6 lg:grid-cols-2">
        {hasRole(["doctor", "nurse", "admin", "receptionist"]) && (
          <Card>
            <CardHeader><CardTitle>Lookup patient by ID</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={onLookup} className="flex gap-2">
                <Input placeholder="Patient UUID" value={lookupId} onChange={(e) => setLookupId(e.target.value)} />
                <Button type="submit" disabled={lookup.isFetching}>Fetch</Button>
              </form>
              {found && <PatientDetails patient={found} />}
            </CardContent>
          </Card>
        )}

        {hasRole("patient") && (
          <Card>
            <CardHeader><CardTitle>Create my profile</CardTitle></CardHeader>
            <CardContent>
              <form
                onSubmit={(e) => { e.preventDefault(); create.mutate(); }}
                className="space-y-3"
              >
                <div>
                  <Label>Name</Label>
                  <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>DOB</Label>
                    <Input type="date" value={form.dob} onChange={(e) => setForm({ ...form, dob: e.target.value })} />
                  </div>
                  <div>
                    <Label>Phone</Label>
                    <Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                  </div>
                </div>
                <div>
                  <Label>Address</Label>
                  <Textarea rows={2} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
                </div>
                <Button type="submit" disabled={create.isPending}>{create.isPending ? "Saving…" : "Create profile"}</Button>
              </form>
              {found && <PatientDetails patient={found} />}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Paginated patient list for staff */}
      {hasRole(["admin", "doctor", "nurse", "receptionist"]) && (
        <Card>
          <CardHeader>
            <CardTitle>
              All Patients
              {paged && (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  {paged.meta.skip + 1}–{Math.min(paged.meta.skip + paged.meta.limit, paged.meta.total)} of {paged.meta.total}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {listQuery.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {listQuery.isError && <p className="text-sm text-destructive">Failed to load patients.</p>}
            {paged && paged.data.length === 0 && (
              <p className="text-sm text-muted-foreground">No patients found.</p>
            )}
            {paged && paged.data.length > 0 && (
              <div className="divide-y rounded-md border">
                {paged.data.map((p) => (
                  <div key={p.id} className="flex items-center justify-between px-4 py-2 text-sm">
                    <div>
                      <span className="font-medium">{p.name}</span>
                      {p.phone && <span className="ml-2 text-muted-foreground">{p.phone}</span>}
                    </div>
                    <span className="font-mono text-xs text-muted-foreground">{p.id.slice(0, 8)}…</span>
                  </div>
                ))}
              </div>
            )}
            {paged && (
              <div className="mt-4 flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={page.prev}
                  disabled={!paged.meta.has_prev || listQuery.isFetching}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={page.next}
                  disabled={!paged.meta.has_next || listQuery.isFetching}
                >
                  Next
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
