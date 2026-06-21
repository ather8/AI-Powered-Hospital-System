import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { requireRole } from "@/lib/route-guard";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export const Route = createFileRoute("/_authenticated/search")({
  beforeLoad: () => requireRole("/search"),
  head: () => ({ meta: [{ title: "Search — Aetheris" }] }),
  component: Page,
});

function Page() {
  const { hasRole } = useAuth();
  // Mirrors backend RBAC exactly: /search/patients and /search/emrs are
  // doctor/nurse/admin only, while /search/appointments also allows
  // receptionist. Previously all three tabs rendered for everyone with
  // sidebar access to this page, so a receptionist would see "Patients"
  // and "EMRs" tabs that just 403'd on submit.
  const canPatients = hasRole(["doctor", "nurse", "admin"]);
  const canAppointments = hasRole(["doctor", "nurse", "admin", "receptionist"]);
  const canEmrs = hasRole(["doctor", "nurse", "admin"]);
  const firstAvailable = canPatients ? "patients" : canAppointments ? "appointments" : canEmrs ? "emrs" : "patients";

  return (
    <div className="space-y-6">
      <PageHeader title="Search" description="Search across patients, appointments, and EMRs." />
      <Tabs defaultValue={firstAvailable} className="max-w-3xl">
        <TabsList>
          {canPatients && <TabsTrigger value="patients">Patients</TabsTrigger>}
          {canAppointments && <TabsTrigger value="appointments">Appointments</TabsTrigger>}
          {canEmrs && <TabsTrigger value="emrs">EMRs</TabsTrigger>}
        </TabsList>
        {canPatients && <TabsContent value="patients"><PatientsSearch /></TabsContent>}
        {canAppointments && <TabsContent value="appointments"><AppointmentsSearch /></TabsContent>}
        {canEmrs && <TabsContent value="emrs"><EmrSearch /></TabsContent>}
      </Tabs>
    </div>
  );
}

interface PatientResult {
  id: string;
  name: string;
  dob: string | null;
  phone: string | null;
  address: string | null;
}

interface AppointmentResult {
  id: string;
  patient_id: string;
  patient_name: string;
  doctor_id: string;
  doctor_name: string;
  scheduled_time: string;
  status: string;
}

interface EmrResult {
  id: string;
  patient_id: string;
  patient_name: string;
  doctor_id: string;
  doctor_name: string;
  diagnosis: string;
  prescription: string | null;
  lab_results: string | null;
  created_at: string;
}

function EmptyState({ shown }: { shown: boolean }) {
  if (!shown) return null;
  return <p className="mt-4 text-sm text-muted-foreground">No results.</p>;
}

function PatientsSearch() {
  // Search by name (and optionally dob/phone to disambiguate) — never by
  // id. No one, admin included, has a patient's UUID memorized.
  const [f, setF] = useState({ name: "", dob: "", phone: "" });
  const m = useMutation({
    mutationFn: () => api.post<PatientResult[]>("/search/patients", { name: f.name || null, dob: f.dob || null, phone: f.phone || null }),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed"),
  });
  return (
    <Card><CardHeader><CardTitle>Search patients</CardTitle></CardHeader><CardContent>
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <div><Label>Name</Label><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
          <div><Label>Date of birth</Label><Input type="date" value={f.dob} onChange={(e) => setF({ ...f, dob: e.target.value })} /></div>
          <div><Label>Phone</Label><Input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></div>
        </div>
        <Button type="submit" disabled={m.isPending}>{m.isPending ? "Searching…" : "Search"}</Button>
      </form>
      {m.data && (
        <ul className="mt-4 divide-y">
          {m.data.map((p) => (
            <li key={p.id} className="py-2">
              <div className="text-sm font-medium">{p.name}</div>
              <div className="text-xs text-muted-foreground">
                {[p.dob, p.phone, p.address].filter(Boolean).join(" · ") || "No additional details"}
              </div>
            </li>
          ))}
        </ul>
      )}
      <EmptyState shown={!!m.data && m.data.length === 0} />
    </CardContent></Card>
  );
}

function AppointmentsSearch() {
  // Search by the doctor's name, not their id — the backend resolves the
  // name to the matching doctor(s) internally.
  const [f, setF] = useState({ doctor_name: "", date: "", status: "" });
  const m = useMutation({
    mutationFn: () => api.post<AppointmentResult[]>("/search/appointments", { doctor_name: f.doctor_name || null, date: f.date || null, status: f.status || null }),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed"),
  });
  return (
    <Card><CardHeader><CardTitle>Search appointments</CardTitle></CardHeader><CardContent>
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <div><Label>Doctor name</Label><Input value={f.doctor_name} onChange={(e) => setF({ ...f, doctor_name: e.target.value })} /></div>
          <div><Label>Date</Label><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></div>
          <div><Label>Status</Label><Input placeholder="scheduled, completed, cancelled" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} /></div>
        </div>
        <Button type="submit" disabled={m.isPending}>{m.isPending ? "Searching…" : "Search"}</Button>
      </form>
      {m.data && (
        <ul className="mt-4 divide-y">
          {m.data.map((a) => (
            <li key={a.id} className="flex items-center justify-between py-2">
              <div>
                <div className="text-sm font-medium">{a.patient_name} with Dr. {a.doctor_name}</div>
                <div className="text-xs text-muted-foreground">{new Date(a.scheduled_time).toLocaleString()}</div>
              </div>
              <Badge variant="outline">{a.status}</Badge>
            </li>
          ))}
        </ul>
      )}
      <EmptyState shown={!!m.data && m.data.length === 0} />
    </CardContent></Card>
  );
}

function EmrSearch() {
  // Search by the patient's name, not their id — the backend resolves
  // the name to the matching patient(s) internally.
  const [f, setF] = useState({ patient_name: "", diagnosis: "", from: "", to: "" });
  const m = useMutation({
    mutationFn: () => api.post<EmrResult[]>("/search/emrs", {
      patient_name: f.patient_name || null,
      diagnosis: f.diagnosis || null,
      date_range: f.from && f.to ? [f.from, f.to] : null,
    }),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed"),
  });
  return (
    <Card><CardHeader><CardTitle>Search EMRs</CardTitle></CardHeader><CardContent>
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="space-y-3">
        <div><Label>Patient name</Label><Input value={f.patient_name} onChange={(e) => setF({ ...f, patient_name: e.target.value })} /></div>
        <div><Label>Diagnosis contains</Label><Input value={f.diagnosis} onChange={(e) => setF({ ...f, diagnosis: e.target.value })} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><Label>From</Label><Input type="date" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value })} /></div>
          <div><Label>To</Label><Input type="date" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })} /></div>
        </div>
        <Button type="submit" disabled={m.isPending}>{m.isPending ? "Searching…" : "Search"}</Button>
      </form>
      {m.data && (
        <ul className="mt-4 divide-y">
          {m.data.map((rec) => (
            <li key={rec.id} className="py-2">
              <div className="text-sm font-medium">{rec.patient_name} — {rec.diagnosis}</div>
              <div className="text-xs text-muted-foreground">
                Dr. {rec.doctor_name} · {new Date(rec.created_at).toLocaleString()}
              </div>
            </li>
          ))}
        </ul>
      )}
      <EmptyState shown={!!m.data && m.data.length === 0} />
    </CardContent></Card>
  );
}
