import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState, useRef, useEffect } from "react";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { AiErrorBoundary } from "@/components/ai-error-boundary";

interface Msg {
  role: "user" | "bot";
  content: string;
  meta?: { disease?: string; severity?: string; department?: string; confidence?: number; classificationAvailable?: boolean };
}

interface ChatbotResponse {
  conversation_reply: string;
  disease: string | null;
  severity: string | null;
  department: string | null;
  confidence: number | null;
  classification_available: boolean;
  disclaimer: string;
  session_id: string;
}

export const Route = createFileRoute("/_authenticated/chatbot")({
  head: () => ({ meta: [{ title: "Triage Chatbot — Aetheris" }] }),
  component: () => (
    <AiErrorBoundary feature="Triage Chatbot">
      <Page />
    </AiErrorBoundary>
  ),
});

function Page() {
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [symptoms, setSymptoms] = useState("");
  const [log, setLog] = useState<Msg[]>([]);
  // Session ID persists across turns so the backend can maintain history.
  const [sessionId, setSessionId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  const m = useMutation({
    mutationFn: () =>
      api.post<ChatbotResponse>("/chatbot/conversation", {
        name,
        age: Number(age),
        symptoms,
        session_id: sessionId,
      }),
    onSuccess: (res) => {
      // Persist the session_id the server echoed back
      if (res.session_id) setSessionId(res.session_id);

      setLog((l) => [
        ...l,
        { role: "user", content: symptoms },
        {
          role: "bot",
          content: res.conversation_reply,
          meta: {
            disease: res.disease ?? undefined,
            severity: res.severity ?? undefined,
            department: res.department ?? undefined,
            confidence: res.confidence ?? undefined,
            classificationAvailable: res.classification_available,
          },
        },
      ]);
      setSymptoms("");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed"),
  });

  const clearMutation = useMutation({
    mutationFn: () =>
      sessionId
        ? api.del(`/chatbot/conversation/${sessionId}`)
        : Promise.resolve(),
    onSuccess: () => {
      setLog([]);
      setSessionId(null);
      setSymptoms("");
    },
    onError: () => {
      // Even if the server call fails, clear the local state
      setLog([]);
      setSessionId(null);
    },
  });

  const severityColor: Record<string, string> = {
    high: "destructive",
    medium: "default",
    low: "secondary",
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Symptom Triage Chatbot"
        description="AI-powered multi-turn triage assistant. Continue the conversation across multiple messages."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Patient input</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                m.mutate();
              }}
              className="space-y-3"
            >
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Name</Label>
                  <Input
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div>
                  <Label>Age</Label>
                  <Input
                    required
                    type="number"
                    min={0}
                    value={age}
                    onChange={(e) => setAge(e.target.value)}
                  />
                </div>
              </div>
              <div>
                <Label>Message / Symptoms</Label>
                <Textarea
                  required
                  rows={4}
                  placeholder="Describe your symptoms or answer the assistant's question…"
                  value={symptoms}
                  onChange={(e) => setSymptoms(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={m.isPending}>
                  {m.isPending ? "Thinking…" : "Send"}
                </Button>
                {log.length > 0 && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => clearMutation.mutate()}
                    disabled={clearMutation.isPending}
                  >
                    New Conversation
                  </Button>
                )}
              </div>
              {sessionId && (
                <p className="text-[10px] text-muted-foreground">
                  Session: {sessionId.slice(0, 8)}…
                </p>
              )}
            </form>
          </CardContent>
        </Card>

        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Conversation</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto max-h-[28rem]">
            {log.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No messages yet. Enter your symptoms to start.
              </p>
            )}
            <ul className="space-y-3">
              {log.map((msg, i) => (
                <li key={i}>
                  {msg.role === "user" ? (
                    <div className="rounded-md bg-secondary p-3 text-sm">
                      <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                        You
                      </div>
                      {msg.content}
                    </div>
                  ) : (
                    <div className="rounded-md border bg-primary/5 p-3 text-sm space-y-2">
                      <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                        Assistant
                      </div>
                      <p className="whitespace-pre-wrap">{msg.content}</p>
                      {msg.meta?.disease && (
                        <div className="flex flex-wrap gap-1 pt-1 border-t">
                          <Badge variant="outline">{msg.meta.disease}</Badge>
                          {msg.meta.department && (
                            <Badge variant="outline">{msg.meta.department}</Badge>
                          )}
                          {msg.meta.severity && (
                            <Badge
                              variant={
                                (severityColor[msg.meta.severity?.toLowerCase()] as
                                  | "destructive"
                                  | "default"
                                  | "secondary") ?? "secondary"
                              }
                            >
                              {msg.meta.severity} severity
                            </Badge>
                          )}
                          {msg.meta.confidence != null && (
                            <Badge variant="secondary">
                              {Math.round(msg.meta.confidence * 100)}% conf.
                            </Badge>
                          )}
                        </div>
                      )}
                      {msg.meta?.classificationAvailable === false && (
                        <p className="pt-1 border-t text-[11px] text-muted-foreground">
                          ⚠️ Symptom classification unavailable — no trained model is installed.
                          The conversational reply above is still active. Please consult a doctor for any diagnosis.
                        </p>
                      )}
                    </div>
                  )}
                </li>
              ))}
              <div ref={bottomRef} />
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
