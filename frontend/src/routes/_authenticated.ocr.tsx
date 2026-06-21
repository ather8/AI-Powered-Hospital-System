import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { API_BASE, ApiError, getToken } from "@/lib/api";
import { requireRole } from "@/lib/route-guard";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const Route = createFileRoute("/_authenticated/ocr")({
  beforeLoad: () => requireRole("/ocr"),
  head: () => ({ meta: [{ title: "OCR — Aetheris" }] }),
  component: Page,
});

function Page() {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const token = getToken();
      const res = await fetch(`${API_BASE}/ocr/extract`, {
        method: "POST",
        body: fd,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) throw new ApiError(res.status, data?.detail ?? "OCR failed", data);
      setText(data.extracted_text);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader title="OCR" description="Extract text from medical images, scans, and forms." />
      <Card className="max-w-2xl">
        <CardHeader><CardTitle>Upload image</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-3">
            <Input type="file" accept="image/*,.pdf" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <Button type="submit" disabled={loading || !file}>{loading ? "Extracting…" : "Extract text"}</Button>
          </form>
          {text && (
            <pre className="mt-6 max-h-[480px] overflow-auto rounded-md border bg-muted/40 p-4 text-sm whitespace-pre-wrap">{text}</pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
