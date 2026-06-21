import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, API_BASE, ApiError, getToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { requireRole } from "@/lib/route-guard";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export const Route = createFileRoute("/_authenticated/emr")({
  beforeLoad: () => requireRole("/emr"),
  head: () => ({ meta: [{ title: "EMR — Aetheris" }] }),
  component: EmrPage,
});

interface EmrRecord {
  id: string;
  patient_id: string;
  doctor_id: string;
  diagnosis: string;
  prescription: string | null;
  lab_results: string | null;
  created_at: string;
}

function EmrPage() {
  const { hasRole } = useAuth();
  const isPatient = hasRole("patient");
  // Backend only lets doctor/nurse create EMR entries — rendering this
  // form for a patient would just produce a 403 on submit with no clear
  // explanation, same class of bug as the lookup-card gate fixed earlier.
  const canCreate = hasRole(["doctor", "nurse"]);
  // Backend export route is admin/doctor only; nurse and patient would
  // get a silent failed download if this button were shown to them.
  const canExport = hasRole(["admin", "doctor"]);

  const [form, setForm] = useState({ patient_id: "", doctor_id: "", diagnosis: "", prescription: "", lab_results: "" });
  const create = useMutation({
    mutationFn: () =>
      api.post("/emrs/", {
        patient_id: form.patient_id,
        doctor_id: form.doctor_id,
        diagnosis: form.diagnosis,
        prescription: form.prescription || null,
        lab_results: form.lab_results || null,
      }),
    onSuccess: () => toast.success("EMR record created"),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed"),
  });

  // Patients view their own history through the dedicated /me route — they
  // never need to know or supply their own Patient UUID.
  const myRecords = useQuery({
    queryKey: ["my-emr"],
    queryFn: () => api.get<EmrRecord[]>("/emrs/me"),
    enabled: isPatient,
  });

  async function downloadCsv() {
    const token = getToken();
    const res = await fetch(`${API_BASE}/export/emr/csv`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!res.ok) { toast.error("Export failed"); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "emr.csv"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Electronic Medical Records" description="Create and export EMR entries." actions={
        canExport ? <Button variant="outline" onClick={downloadCsv}>Export CSV</Button> : null
      } />
      {canCreate && (
        <Card className="max-w-2xl">
          <CardHeader><CardTitle>New EMR entry</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Patient ID</Label><Input required value={form.patient_id} onChange={(e) => setForm({ ...form, patient_id: e.target.value })} /></div>
                <div><Label>Doctor ID</Label><Input required value={form.doctor_id} onChange={(e) => setForm({ ...form, doctor_id: e.target.value })} /></div>
              </div>
              <div><Label>Diagnosis</Label><Textarea required rows={2} value={form.diagnosis} onChange={(e) => setForm({ ...form, diagnosis: e.target.value })} /></div>
              <div><Label>Prescription</Label><Textarea rows={3} value={form.prescription} onChange={(e) => setForm({ ...form, prescription: e.target.value })} /></div>
              <div><Label>Lab results</Label><Textarea rows={3} value={form.lab_results} onChange={(e) => setForm({ ...form, lab_results: e.target.value })} /></div>
              <Button type="submit" disabled={create.isPending}>{create.isPending ? "Saving…" : "Save record"}</Button>
            </form>
          </CardContent>
        </Card>
      )}
      {isPatient && (
        <Card className="max-w-2xl">
          <CardHeader><CardTitle>Your medical records</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {myRecords.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {myRecords.isError && <p className="text-sm text-muted-foreground">No records on file yet.</p>}
            {myRecords.data?.length === 0 && <p className="text-sm text-muted-foreground">No records on file yet.</p>}
            {myRecords.data?.map((r) => (
              <div key={r.id} className="rounded-md border p-3 text-sm">
                <div className="flex items-center justify-between">
                  <div className="font-medium">{r.diagnosis}</div>
                  <div className="text-xs text-muted-foreground">{new Date(r.created_at).toLocaleDateString()}</div>
                </div>
                {r.prescription && <div className="mt-1 text-muted-foreground">Prescription: {r.prescription}</div>}
                {r.lab_results && <div className="mt-1 text-muted-foreground">Lab results: {r.lab_results}</div>}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
