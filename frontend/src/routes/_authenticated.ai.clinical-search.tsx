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

export const Route = createFileRoute("/_authenticated/ai/clinical-search")({
  beforeLoad: () => requireRole("/ai/clinical-search"),
  head: () => ({ meta: [{ title: "Clinical Search — Aetheris" }] }),
  component: () => (
    <AiErrorBoundary feature="AI Clinical Search">
      <Page />
    </AiErrorBoundary>
  ),
});

interface SearchResponse {
  answer?: string;
  status?: string;
  detail?: string;
}

function Page() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);

  const m = useMutation({
    mutationFn: () =>
      api.post<SearchResponse>("/ai-clinical-search/", { query }),
    onSuccess: (r) => setResult(r),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Search failed"),
  });

  const isDisabled = result?.status === "disabled";

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Clinical Search"
        description="Ask clinical questions backed by your guidelines database."
      />
      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Query</CardTitle>
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
              rows={3}
              placeholder="e.g. First-line treatment for community-acquired pneumonia in adults"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Button type="submit" disabled={m.isPending}>
              {m.isPending ? "Searching…" : "Search"}
            </Button>
          </form>

          {/* Loading skeleton */}
          {m.isPending && (
            <div className="mt-6">
              <AiLoadingSkeleton lines={5} label="Searching guidelines…" />
            </div>
          )}

          {/* RAG pipeline disabled */}
          {!m.isPending && isDisabled && (
            <div className="mt-6">
              <AiUnavailableBanner
                detail={
                  result?.detail ??
                  "The clinical search index is not built. Run 'python build_faiss_index.py' in the backend directory."
                }
              />
            </div>
          )}

          {/* Success */}
          {!m.isPending && result?.answer && (
            <div className="mt-6 rounded-md border bg-muted/40 p-4 text-sm leading-relaxed whitespace-pre-wrap">
              {result.answer}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
