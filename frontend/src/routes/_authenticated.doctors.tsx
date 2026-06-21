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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface Doctor {
  id: string;
  name: string;
  specialty: string;
  experience_years: number | null;
  available: boolean;
  user_id: number | null;
}

interface UnlinkedUser {
  id: number;
  email: string;
}

interface PagedDoctors {
  data: Doctor[];
  meta: { total: number; skip: number; limit: number; has_next: boolean; has_prev: boolean };
}

const UNLINKED_NONE = "__none__";

export const Route = createFileRoute("/_authenticated/doctors")({
  head: () => ({ meta: [{ title: "Doctors — Aetheris" }] }),
  component: DoctorsPage,
});

function DoctorsPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["doctors"], queryFn: () => api.get<PagedDoctors>("/doctors/") });
  const unlinkedUsers = useQuery({
    queryKey: ["doctors", "unlinked-users"],
    queryFn: () => api.get<UnlinkedUser[]>("/doctors/unlinked-users"),
    enabled: hasRole("admin"),
  });
  const [form, setForm] = useState({ name: "", specialty: "", experience_years: "", user_id: UNLINKED_NONE });

  const create = useMutation({
    mutationFn: () =>
      api.post<Doctor>("/doctors/", {
        name: form.name,
        specialty: form.specialty,
        experience_years: form.experience_years ? Number(form.experience_years) : null,
        user_id: form.user_id === UNLINKED_NONE ? null : Number(form.user_id),
      }),
    onSuccess: () => {
      toast.success("Doctor added");
      setForm({ name: "", specialty: "", experience_years: "", user_id: UNLINKED_NONE });
      qc.invalidateQueries({ queryKey: ["doctors"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed"),
  });

  const link = useMutation({
    mutationFn: ({ doctorId, userId }: { doctorId: string; userId: number | null }) =>
      api.put<Doctor>(`/doctors/${doctorId}`, { user_id: userId }),
    onSuccess: () => {
      toast.success("Doctor account updated");
      qc.invalidateQueries({ queryKey: ["doctors"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed"),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Doctors" description="Hospital clinicians directory." />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Roster</CardTitle></CardHeader>
          <CardContent>
            {list.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {list.error && <p className="text-sm text-destructive">{(list.error as Error).message}</p>}
            {list.data && list.data.data.length === 0 && <p className="text-sm text-muted-foreground">No doctors yet.</p>}
            <ul className="divide-y">
              {list.data?.data?.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-4 py-3">
                  <div>
                    <div className="font-medium">{d.name}</div>
                    <div className="text-xs text-muted-foreground">{d.specialty} · {d.experience_years ?? 0} yrs</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={d.user_id ? "outline" : "secondary"} className="shrink-0">
                      {d.user_id ? "Account linked" : "No login linked"}
                    </Badge>
                    <Badge variant={d.available ? "default" : "secondary"}>{d.available ? "Available" : "Off"}</Badge>
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {hasRole("admin") && (
          <div className="space-y-6">
            <Card>
              <CardHeader><CardTitle>Add doctor</CardTitle></CardHeader>
              <CardContent>
                <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="space-y-3">
                  <div><Label>Name</Label><Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
                  <div><Label>Specialty</Label><Input required value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} /></div>
                  <div><Label>Experience (years)</Label><Input type="number" min={0} value={form.experience_years} onChange={(e) => setForm({ ...form, experience_years: e.target.value })} /></div>
                  <div>
                    <Label>Linked login account</Label>
                    <Select value={form.user_id} onValueChange={(v) => setForm({ ...form, user_id: v })}>
                      <SelectTrigger className="mt-1.5"><SelectValue placeholder="None (link later)" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value={UNLINKED_NONE}>None (link later)</SelectItem>
                        {unlinkedUsers.data?.map((u) => (
                          <SelectItem key={u.id} value={String(u.id)}>{u.email}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Only User accounts with role "doctor" that aren't already linked show up here.
                    </p>
                  </div>
                  <Button type="submit" disabled={create.isPending}>{create.isPending ? "Saving…" : "Add"}</Button>
                </form>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Link an existing profile</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-xs text-muted-foreground">
                  Doctor profiles without a linked account can't see their own dashboard/appointments — only hospital-wide data. Link one below.
                </p>
                {list.data?.data?.filter((d) => !d.user_id).map((d) => (
                  <div key={d.id} className="flex items-center gap-2">
                    <div className="flex-1 truncate text-sm">{d.name}</div>
                    <Select onValueChange={(v) => link.mutate({ doctorId: d.id, userId: Number(v) })}>
                      <SelectTrigger className="w-44 shrink-0"><SelectValue placeholder="Link account" /></SelectTrigger>
                      <SelectContent>
                        {unlinkedUsers.data?.map((u) => (
                          <SelectItem key={u.id} value={String(u.id)}>{u.email}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
                {list.data?.data?.filter((d) => !d.user_id).length === 0 && (
                  <p className="text-sm text-muted-foreground">Every doctor profile is linked.</p>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

