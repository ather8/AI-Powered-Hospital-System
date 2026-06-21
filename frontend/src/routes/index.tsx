import { createFileRoute, Link } from "@tanstack/react-router";
import { Brain, ClipboardList, CalendarClock, ShieldCheck, Stethoscope, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Aetheris — AI Hospital Platform" },
      { name: "description", content: "Unified, AI-assisted hospital management: EMR, scheduling, billing, clinical AI, and analytics." },
    ],
  }),
  component: Landing,
});

function Landing() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold">A</div>
            <span className="font-semibold tracking-tight">Aetheris Health</span>
          </Link>
          <nav className="flex items-center gap-2">
            <Button asChild variant="ghost"><Link to="/login">Sign in</Link></Button>
            <Button asChild><Link to="/register">Get started</Link></Button>
          </nav>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-24">
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" /> Built for modern clinical workflows
          </span>
          <h1 className="mt-6 text-5xl font-semibold tracking-tight text-foreground sm:text-6xl">
            A calmer way to run your hospital.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
            Aetheris unifies patients, appointments, EMR, billing, and AI-assisted triage,
            summarization, and clinical search — in one secure platform.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg"><Link to="/register">Create account</Link></Button>
            <Button asChild size="lg" variant="outline"><Link to="/login">Sign in</Link></Button>
          </div>
        </div>

        <div className="mt-20 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { icon: ClipboardList, title: "Electronic Medical Records", desc: "Structured patient histories with role-based access." },
            { icon: CalendarClock, title: "Smart scheduling", desc: "Appointments with status tracking and reminders." },
            { icon: Brain, title: "Clinical AI", desc: "Symptom triage, report summaries, and clinical search." },
            { icon: Stethoscope, title: "Doctor & staff workflows", desc: "RBAC for admins, doctors, nurses, and reception." },
            { icon: Activity, title: "OCR & document intake", desc: "Extract text and structure from scans and PDFs." },
            { icon: ShieldCheck, title: "Audit-ready", desc: "Every action logged. Compliant by design." },
          ].map((f) => (
            <div key={f.title} className="rounded-xl border bg-card p-6 shadow-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <f.icon className="h-5 w-5" />
              </div>
              <h3 className="mt-4 text-base font-semibold">{f.title}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6 text-xs text-muted-foreground">
          <span>© {new Date().getFullYear()} Aetheris Health</span>
          <span>Connected to FastAPI backend</span>
        </div>
      </footer>
    </div>
  );
}
