import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { requireRole } from "@/lib/route-guard";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { AiErrorBoundary } from "@/components/ai-error-boundary";
import { AiLoadingSkeleton } from "@/components/ai-loading-skeleton";

export const Route = createFileRoute("/_authenticated/ai/notes")({
  beforeLoad: () => requireRole("/ai/notes"),
  head: () => ({ meta: [{ title: "AI Notes — Aetheris" }] }),
  component: () => (
    <AiErrorBoundary feature="AI Notes">
      <Page />
    </AiErrorBoundary>
  ),
});

function Page() {
  const [raw, setRaw] = useState("");
  const [note, setNote] = useState<string | null>(null);

  const m = useMutation({
    mutationFn: () =>
      api.post<{ structured_note: string }>("/ai-notes/", { raw_text: raw }),
    onSuccess: (r) => setNote(r.structured_note),
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Failed to generate note"),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Notes"
        description="Turn free-form dictation into structured clinical notes."
      />
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Raw notes</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              m.mutate();
            }}
            className="space-y-3"
          >
            <Textarea
              required
              rows={8}
              placeholder="Dictate or paste unstructured clinical notes here…"
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
            />
            <Button type="submit" disabled={m.isPending}>
              {m.isPending ? "Structuring…" : "Generate note"}
            </Button>
          </form>

          {/* Loading skeleton */}
          {m.isPending && (
            <div className="mt-6">
              <AiLoadingSkeleton lines={7} label="Structuring your notes…" />
            </div>
          )}

          {/* Result */}
          {!m.isPending && note && (
            <div className="mt-6 rounded-md border bg-muted/40 p-4 text-sm leading-relaxed whitespace-pre-wrap">
              {note}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
