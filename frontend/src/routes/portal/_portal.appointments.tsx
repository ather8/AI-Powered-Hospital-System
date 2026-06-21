/**
 * Patient Portal — Appointments
 * Patient-focused appointment booking and management.
 * Reuses the same backend endpoints as the staff view but with
 * simplified, patient-friendly language and the slot picker always visible.
 */
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CalendarClock, UserPlus } from "lucide-react";

export const Route = createFileRoute("/portal/_portal/appointments")({
  head: () => ({ meta: [{ title: "My Appointments — Aetheris" }] }),
  component: PortalAppointments,
});

interface Appointment {
  id: string;
  doctor_id: string;
  scheduled_time: string;
  status: string;
  department: string | null;
}
interface Doctor { id: string; name: string; specialty: string; available: boolean }
interface PagedAppt { data: Appointment[]; meta: { total: number; page: number; pages: number } }
interface MyPatient { id: string; name: string }

function slotLabel(iso: string) {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function statusVariant(s: string): "default" | "secondary" | "destructive" {
  if (s === "scheduled") return "default";
  if (s === "cancelled") return "destructive";
  return "secondary";
}

function PortalAppointments() {
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    doctor_id: "",
    date: "",
    scheduled_time: "",
    department: "",
  });
  const [reschedulingId, setReschedulingId] = useState<string | null>(null);
  const [newTime, setNewTime] = useState("");

  // A freshly-registered patient has no Patient record yet, and booking
  // will 400 until one exists. Check proactively so the booking form can
  // show a clear "create your profile first" prompt instead of a patient
  // filling out the whole form just to hit an error at the end.
  const myProfileQ = useQuery({
    queryKey: ["portal-my-patient"],
    queryFn: () => api.get<MyPatient>("/patients/me"),
    retry: false,
    // A 404 here just means "no profile yet" — not a real error — so
    // don't let React Query treat it as a failed query that retries/logs.
    throwOnError: false,
  });
  const hasProfile = !!myProfileQ.data;
  const profileCheckDone = myProfileQ.isFetched;

  const doctorsQ = useQuery({
    queryKey: ["doctors"],
    queryFn: () => api.get<{ data: Doctor[] }>("/doctors/"),
  });

  const apptsQ = useQuery({
    queryKey: ["portal-appointments"],
    queryFn: () => api.get<PagedAppt>("/appointments/"),
  });

  const slotsQ = useQuery({
    queryKey: ["slots", form.doctor_id, form.date],
    queryFn: () =>
      api.get<string[]>(
        `/appointments/available?doctor_id=${form.doctor_id}&date=${form.date}`
      ),
    enabled: !!(form.doctor_id && form.date),
  });

  const book = useMutation({
    mutationFn: () =>
      api.post<Appointment>("/appointments/", {
        doctor_id: form.doctor_id,
        scheduled_time: form.scheduled_time,
        ...(form.department ? { department: form.department } : {}),
      }),
    onSuccess: () => {
      toast.success("Appointment booked!");
      setForm({ doctor_id: "", date: "", scheduled_time: "", department: "" });
      qc.invalidateQueries({ queryKey: ["portal-appointments"] });
      qc.invalidateQueries({ queryKey: ["slots"] });
    },
    onError: (e) => {
      // Safety net behind the proactive hasProfile check above, in case
      // the profile was deleted/never synced between tabs.
      if (e instanceof ApiError && e.status === 400 && /patient profile/i.test(e.message)) {
        toast.error("Create your patient profile first.");
        navigate({ to: "/portal/create-profile", search: { redirect: "/portal/appointments" } });
        return;
      }
      toast.error(e instanceof ApiError ? e.message : "Booking failed");
    },
  });

  const reschedule = useMutation({
    mutationFn: ({ id, time }: { id: string; time: string }) =>
      api.put<Appointment>(`/appointments/${id}`, { scheduled_time: time }),
    onSuccess: () => {
      toast.success("Appointment rescheduled");
      setReschedulingId(null);
      setNewTime("");
      qc.invalidateQueries({ queryKey: ["portal-appointments"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Rescheduling failed"),
  });

  const cancel = useMutation({
    mutationFn: (id: string) =>
      api.put<Appointment>(`/appointments/${id}`, { status: "cancelled" }),
    onSuccess: () => {
      toast.success("Appointment cancelled");
      qc.invalidateQueries({ queryKey: ["portal-appointments"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Cancellation failed"),
  });

  const appts = apptsQ.data?.data ?? [];
  const doctors = doctorsQ.data?.data ?? [];
  const slots = slotsQ.data ?? [];
  const upcomingAppts = appts.filter((a) => a.status === "scheduled");
  const pastAppts = appts.filter((a) => a.status !== "scheduled");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Appointments</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Book a new visit or manage your upcoming appointments.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Booking form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CalendarClock className="h-4 w-4" />
              Book a new appointment
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {profileCheckDone && !hasProfile ? (
              <div className="flex flex-col items-center gap-3 rounded-md border border-dashed py-8 text-center">
                <UserPlus className="h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  Create your patient profile to start booking appointments.
                </p>
                <Link to="/portal/create-profile" search={{ redirect: "/portal/appointments" }}>
                  <Button size="sm">Create my profile</Button>
                </Link>
              </div>
            ) : (
              <>
                {doctorsQ.isLoading && <Skeleton className="h-9 w-full" />}
                {doctorsQ.data && (
                  <>
                    <div>
                      <Label>Choose a doctor</Label>
                      <select
                        className="mt-1.5 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                        value={form.doctor_id}
                        onChange={(e) =>
                          setForm({ ...form, doctor_id: e.target.value, date: "", scheduled_time: "" })
                        }
                      >
                        <option value="" disabled>Select a doctor…</option>
                        {doctors.map((d) => (
                          <option key={d.id} value={d.id} disabled={!d.available}>
                            Dr. {d.name} — {d.specialty}
                            {!d.available ? " (unavailable)" : ""}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <Label>Reason / Department <span className="text-muted-foreground">(optional)</span></Label>
                      <Input
                        value={form.department}
                        placeholder="e.g. Follow-up, Cardiology"
                        onChange={(e) => setForm({ ...form, department: e.target.value })}
                      />
                    </div>

                    {form.doctor_id && (
                      <div>
                        <Label>Select a date</Label>
                        <Input
                          type="date"
                          value={form.date}
                          min={new Date().toISOString().slice(0, 10)}
                          onChange={(e) =>
                            setForm({ ...form, date: e.target.value, scheduled_time: "" })
                          }
                        />
                      </div>
                    )}

                    {form.date && (
                      <div>
                        <Label>Available times</Label>
                        {slotsQ.isLoading && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            Checking availability…
                          </p>
                        )}
                        {slotsQ.isSuccess && slots.length === 0 && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            No slots available on this date — please choose another day.
                          </p>
                        )}
                        {slots.length > 0 && (
                          <div className="mt-1.5 flex flex-wrap gap-2">
                            {slots.map((iso) => (
                              <button
                                key={iso}
                                type="button"
                                onClick={() => setForm({ ...form, scheduled_time: iso })}
                                className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                                  form.scheduled_time === iso
                                    ? "border-primary bg-primary text-primary-foreground"
                                    : "border-input hover:bg-muted"
                                }`}
                              >
                                {slotLabel(iso)}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    <Button
                      className="w-full"
                      disabled={!form.scheduled_time || book.isPending}
                      onClick={() => book.mutate()}
                    >
                      {book.isPending ? "Booking…" : "Confirm booking"}
                    </Button>
                  </>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Upcoming appointments */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Upcoming ({upcomingAppts.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {apptsQ.isLoading && (
                <div className="space-y-2">
                  <Skeleton className="h-12" />
                  <Skeleton className="h-12" />
                </div>
              )}
              {upcomingAppts.length === 0 && !apptsQ.isLoading && (
                <p className="text-sm text-muted-foreground">No upcoming appointments.</p>
              )}
              <ul className="divide-y">
                {upcomingAppts.map((a) => {
                  const doc = doctors.find((d) => d.id === a.doctor_id);
                  const isRescheduling = reschedulingId === a.id;
                  return (
                    <li key={a.id} className="py-3">
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="font-medium">
                            Dr. {doc?.name ?? "Unknown"}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {new Date(a.scheduled_time).toLocaleString([], {
                              weekday: "short",
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </div>
                          {a.department && (
                            <div className="text-xs text-muted-foreground">
                              {a.department}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5">
                          <Badge variant={statusVariant(a.status)}>{a.status}</Badge>
                          {!isRescheduling && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setReschedulingId(a.id);
                                  setNewTime("");
                                }}
                              >
                                Reschedule
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={cancel.isPending}
                                onClick={() => cancel.mutate(a.id)}
                              >
                                Cancel
                              </Button>
                            </>
                          )}
                        </div>
                      </div>
                      {isRescheduling && (
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
                            onClick={() =>
                              reschedule.mutate({
                                id: a.id,
                                time: new Date(newTime).toISOString(),
                              })
                            }
                          >
                            {reschedule.isPending ? "Saving…" : "Save"}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setReschedulingId(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </CardContent>
          </Card>

          {pastAppts.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Past appointments</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="divide-y">
                  {pastAppts.slice(0, 5).map((a) => {
                    const doc = doctors.find((d) => d.id === a.doctor_id);
                    return (
                      <li key={a.id} className="flex items-center justify-between py-2">
                        <div>
                          <div className="text-sm font-medium">
                            Dr. {doc?.name ?? "Unknown"}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {new Date(a.scheduled_time).toLocaleDateString()}
                          </div>
                        </div>
                        <Badge variant={statusVariant(a.status)}>{a.status}</Badge>
                      </li>
                    );
                  })}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
