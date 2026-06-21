/**
 * Patient Portal — Create My Profile
 *
 * A freshly-registered patient has a User row but no Patient row yet.
 * POST /appointments/ (and other patient actions) return a 400
 * ("Create your patient profile before booking an appointment.") until
 * one exists. This page is where that 400 should send them, and it's
 * also reachable directly from the portal nav so a new patient can find
 * it without having to trip the error first.
 *
 * Backed by POST /patients/ — patients don't pass user_id, the backend
 * binds it to their own JWT sub.
 */
import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { UserPlus } from "lucide-react";

interface Patient {
  id: string;
  name: string;
  dob: string | null;
  phone: string | null;
  address: string | null;
}

export const Route = createFileRoute("/portal/_portal/create-profile")({
  head: () => ({ meta: [{ title: "Create My Profile — Aetheris" }] }),
  validateSearch: (search: Record<string, unknown>) => ({
    redirect: typeof search.redirect === "string" ? search.redirect : undefined,
  }),
  component: CreateProfilePage,
});

function CreateProfilePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { redirect } = useSearch({ from: "/_portal/create-profile" });

  const [form, setForm] = useState({ name: "", dob: "", phone: "", address: "" });

  // If a profile already exists, don't show the form again — bounce the
  // patient straight to where they were headed (or the overview).
  const existing = useQuery({
    queryKey: ["portal-my-patient"],
    queryFn: () => api.get<Patient>("/patients/me"),
    retry: false,
  });

  const create = useMutation({
    mutationFn: () =>
      api.post<Patient>("/patients/", {
        name: form.name,
        dob: form.dob || null,
        phone: form.phone || null,
        address: form.address || null,
      }),
    onSuccess: () => {
      toast.success("Profile created");
      qc.invalidateQueries({ queryKey: ["portal-my-patient"] });
      navigate({ to: redirect || "/portal/overview" });
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 409) {
        // Profile already exists (race: created in another tab, or a
        // stale "no profile" check) — just move on instead of erroring.
        toast.info("You already have a profile on file.");
        navigate({ to: redirect || "/portal/overview" });
        return;
      }
      toast.error(e instanceof ApiError ? e.message : "Could not create your profile");
    },
  });

  if (existing.data) {
    navigate({ to: redirect || "/portal/overview" });
  }

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Create your patient profile</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          We need a few details before you can book appointments, view bills,
          or see your records.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <UserPlus className="h-4 w-4" />
            Your details
          </CardTitle>
          <CardDescription>
            You can update these later from your profile.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <div>
              <Label htmlFor="name">Full name</Label>
              <Input
                id="name"
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="mt-1.5"
                placeholder="Jane Doe"
              />
            </div>
            <div>
              <Label htmlFor="dob">Date of birth</Label>
              <Input
                id="dob"
                type="date"
                value={form.dob}
                onChange={(e) => setForm({ ...form, dob: e.target.value })}
                className="mt-1.5"
                max={new Date().toISOString().slice(0, 10)}
              />
            </div>
            <div>
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                type="tel"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                className="mt-1.5"
                placeholder="(555) 123-4567"
              />
            </div>
            <div>
              <Label htmlFor="address">Address</Label>
              <Input
                id="address"
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                className="mt-1.5"
                placeholder="123 Main St, Springfield"
              />
            </div>
            <Button type="submit" className="w-full" disabled={!form.name || create.isPending}>
              {create.isPending ? "Saving…" : "Save and continue"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
