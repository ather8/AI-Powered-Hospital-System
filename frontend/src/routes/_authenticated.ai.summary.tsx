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
import { AiLoadingSkeleton, AiUnavailableBanner } from "@/components/ai-loading-skeleton";

export const Route = createFileRoute("/_authenticated/ai/summary")({
  beforeLoad: () => requireRole("/ai/summary"),
  head: () => ({ meta: [{ title: "AI Summary — Aetheris" }] }),
  component: () => (
    <AiErrorBoundary feature="AI Report Summary">
      <Page />
    </AiErrorBoundary>
  ),
});

interface SummaryResponse {
  summary?: string;
  status?: string;
  detail?: string;
}

function Page() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<SummaryResponse | null>(null);

  const m = useMutation({
    mutationFn: () =>
      api.post<SummaryResponse>("/ai-summary/", { report_text: text }),
    onSuccess: (r) => setResult(r),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to summarize"),
  });

  const isDisabled = result?.status === "disabled";

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Report Summary"
        description="Paste a medical report to generate a structured summary."
      />
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Report text</CardTitle>
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
              rows={10}
              placeholder="Paste the full medical report here…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <Button type="submit" disabled={m.isPending}>
              {m.isPending ? "Summarizing…" : "Summarize"}
            </Button>
          </form>

          {/* Loading skeleton */}
          {m.isPending && (
            <div className="mt-6">
              <AiLoadingSkeleton lines={6} label="Generating summary…" />
            </div>
          )}

          {/* Disabled / error state */}
          {!m.isPending && isDisabled && (
            <div className="mt-6">
              <AiUnavailableBanner detail={result?.detail} />
            </div>
          )}

          {/* Success */}
          {!m.isPending && result?.summary && (
            <div className="mt-6 rounded-md border bg-muted/40 p-4 text-sm leading-relaxed whitespace-pre-wrap">
              {result.summary}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
