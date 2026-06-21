import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  scheduled_time: string;
  status: string;
  department: string | null;
}

interface Doctor {
  id: string;
  name: string;
  specialty: string;
  available: boolean;
}

export const Route = createFileRoute("/_authenticated/appointments")({
  head: () => ({ meta: [{ title: "Appointments — Aetheris" }] }),
  component: AppointmentsPage,
});

// ---------------------------------------------------------------------------
// Appointment row (list)
// ---------------------------------------------------------------------------

function AppointmentRow({
  appointment,
  doctorName,
  canManage,
}: {
  appointment: Appointment;
  doctorName: string;
  canManage: boolean;
}) {
  const qc = useQueryClient();
  const [rescheduling, setRescheduling] = useState(false);
  const [newTime, setNewTime] = useState("");

  const isActive = appointment.status === "scheduled";

  const reschedule = useMutation({
    mutationFn: (scheduled_time: string) =>
      api.put<Appointment>(`/appointments/${appointment.id}`, { scheduled_time }),
    onSuccess: () => {
      toast.success("Appointment rescheduled");
      setRescheduling(false);
      qc.invalidateQueries({ queryKey: ["appointments"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Failed to reschedule"),
  });

  const cancel = useMutation({
    mutationFn: () =>
      api.put<Appointment>(`/appointments/${appointment.id}`, { status: "cancelled" }),
    onSuccess: () => {
      toast.success("Appointment cancelled");
      qc.invalidateQueries({ queryKey: ["appointments"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Failed to cancel"),
  });

  return (
    <li className="py-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="font-medium">{doctorName}</div>
          <div className="text-xs text-muted-foreground">
            {new Date(appointment.scheduled_time).toLocaleString()}
          </div>
          {appointment.department && (
            <div className="text-xs text-muted-foreground">Dept: {appointment.department}</div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {canManage && isActive && !rescheduling && (
            <>
              <Button size="sm" variant="outline" onClick={() => setRescheduling(true)}>
                Reschedule
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={cancel.isPending}
                onClick={() => cancel.mutate()}
              >
                {cancel.isPending ? "Cancelling…" : "Cancel"}
              </Button>
            </>
          )}
          <Badge variant={appointment.status === "scheduled" ? "default" : "secondary"}>
            {appointment.status}
          </Badge>
        </div>
      </div>

      {/* Reschedule inline form */}
      {rescheduling && (
        <div className="mt-2 flex items-center gap-2">
          <Input
            type="datetime-local"
            value={newTime}
            onChange={(e) => setNewTime(e.target.value)}
            className="max-w-xs"
          />
          <Button
            size="sm"
            disabled={!newTime || reschedule.isPending}
            onClick={() => reschedule.mutate(new Date(newTime).toISOString())}
          >
            {reschedule.isPending ? "Saving…" : "Save"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setRescheduling(false)}>
            Cancel
          </Button>
        </div>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Booking form
// ---------------------------------------------------------------------------

function BookingForm({ isPatient, doctors }: { isPatient: boolean; doctors: Doctor[] }) {
  const qc = useQueryClient();

  const [form, setForm] = useState({
    patient_id: "",
    doctor_id: "",
    date: "",          // YYYY-MM-DD — used to fetch available slots
    scheduled_time: "", // ISO string chosen from available slots
    department: "",
  });

  // Fetch free slots whenever both doctor and date are chosen
  const slotsQuery = useQuery({
    queryKey: ["available-slots", form.doctor_id, form.date],
    queryFn: () =>
      api.get<string[]>(
        `/appointments/available?doctor_id=${form.doctor_id}&date=${form.date}`
      ),
    enabled: !!(form.doctor_id && form.date),
  });

  const create = useMutation({
    mutationFn: () =>
      api.post<Appointment>("/appointments/", {
        ...(isPatient ? {} : { patient_id: form.patient_id }),
        doctor_id: form.doctor_id,
        scheduled_time: form.scheduled_time,
        ...(form.department ? { department: form.department } : {}),
      }),
    onSuccess: () => {
      toast.success("Appointment booked");
      setForm({ patient_id: "", doctor_id: "", date: "", scheduled_time: "", department: "" });
      qc.invalidateQueries({ queryKey: ["appointments"] });
      qc.invalidateQueries({ queryKey: ["available-slots"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to book"),
  });

  const slots = slotsQuery.data ?? [];

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
      className="space-y-3"
    >
      {!isPatient && (
        <div>
          <Label>Patient ID</Label>
          <Input
            required
            value={form.patient_id}
            onChange={(e) => setForm({ ...form, patient_id: e.target.value })}
            placeholder="Patient UUID"
          />
        </div>
      )}

      <div>
        <Label>Doctor</Label>
        <select
          required
          className="mt-1.5 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
          value={form.doctor_id}
          onChange={(e) =>
            setForm({ ...form, doctor_id: e.target.value, date: "", scheduled_time: "" })
          }
        >
          <option value="" disabled>Select a doctor</option>
          {doctors.map((d) => (
            <option key={d.id} value={d.id} disabled={!d.available}>
              {d.name} — {d.specialty}{!d.available ? " (unavailable)" : ""}
            </option>
          ))}
        </select>
      </div>

      <div>
        <Label>Department <span className="text-muted-foreground">(optional)</span></Label>
        <Input
          value={form.department}
          onChange={(e) => setForm({ ...form, department: e.target.value })}
          placeholder="e.g. Cardiology"
        />
      </div>

      {/* Step 2: pick a date to see available slots */}
      {form.doctor_id && (
        <div>
          <Label>Date</Label>
          <Input
            required
            type="date"
            value={form.date}
            onChange={(e) =>
              setForm({ ...form, date: e.target.value, scheduled_time: "" })
            }
          />
        </div>
      )}

      {/* Step 3: pick from available slots only */}
      {form.date && (
        <div>
          <Label>Available time slots</Label>
          {slotsQuery.isLoading && (
            <p className="text-xs text-muted-foreground mt-1">Checking availability…</p>
          )}
          {slotsQuery.isError && (
            <p className="text-xs text-destructive mt-1">
              Couldn't load slots: {(slotsQuery.error as Error).message}
            </p>
          )}
          {slotsQuery.isSuccess && slots.length === 0 && (
            <p className="text-xs text-muted-foreground mt-1">
              No slots available on this date. Please choose another day.
            </p>
          )}
          {slots.length > 0 && (
            <select
              required
              className="mt-1.5 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              value={form.scheduled_time}
              onChange={(e) => setForm({ ...form, scheduled_time: e.target.value })}
            >
              <option value="" disabled>Select a time</option>
              {slots.map((iso) => (
                <option key={iso} value={iso}>
                  {new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </option>
              ))}
            </select>
          )}
        </div>
      )}

      <Button
        type="submit"
        disabled={create.isPending || !form.scheduled_time}
      >
        {create.isPending ? "Booking…" : "Book"}
      </Button>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function AppointmentsPage() {
  const { hasRole } = useAuth();
  const isPatient = hasRole("patient");
  const canSeeList = hasRole(["patient", "admin", "receptionist", "doctor", "nurse"]);

  const doctors = useQuery({
    queryKey: ["doctors"],
    queryFn: () => api.get<{ data: Doctor[] }>("/doctors/"),
  });

  const appointments = useQuery({
    queryKey: ["appointments"],
    queryFn: () => api.get<{ data: Appointment[] }>("/appointments/"),
    enabled: canSeeList,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Appointments"
        description="Book and manage clinical appointments."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Book appointment</CardTitle></CardHeader>
          <CardContent>
            {doctors.isLoading && (
              <p className="text-sm text-muted-foreground">Loading doctors…</p>
            )}
            {doctors.error && (
              <p className="text-sm text-destructive">
                Couldn't load doctors: {(doctors.error as Error).message}
              </p>
            )}
            {doctors.data && (
              <BookingForm isPatient={isPatient} doctors={doctors.data.data} />
            )}
          </CardContent>
        </Card>

        {canSeeList && (
          <Card>
            <CardHeader>
              <CardTitle>{isPatient ? "Your appointments" : "All appointments"}</CardTitle>
            </CardHeader>
            <CardContent>
              {appointments.isLoading && (
                <p className="text-sm text-muted-foreground">Loading…</p>
              )}
              {appointments.error && (
                <p className="text-sm text-destructive">
                  {(appointments.error as Error).message}
                </p>
              )}
              {appointments.data?.data?.length === 0 && (
                <p className="text-sm text-muted-foreground">No appointments yet.</p>
              )}
              <ul className="divide-y">
                {appointments.data?.data?.map((a) => {
                  const doctor = doctors.data?.data?.find((d) => d.id === a.doctor_id);
                  return (
                    <AppointmentRow
                      key={a.id}
                      appointment={a}
                      doctorName={doctor?.name ?? "Unknown doctor"}
                      canManage={isPatient}
                    />
                  );
                })}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
