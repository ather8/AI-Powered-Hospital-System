import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { apiFetch, api, API_BASE, ApiError, getToken, STRIPE_WEBHOOK_SECRET } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useAuth } from "@/lib/auth";
import { requireRole } from "@/lib/route-guard";

export const Route = createFileRoute("/_authenticated/billing")({
  beforeLoad: () => requireRole("/billing"),
  head: () => ({ meta: [{ title: "Billing — Aetheris" }] }),
  component: BillingPage,
});

interface LineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
}

interface Bill {
  id: string;
  patient_id: string;
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  amount: number;
  status: string;
  method: string | null;
  created_at: string;
  line_items: LineItem[];
}

// /billing/me and /billing/{patient_id} both return the shared paginated
// envelope ({ data, meta }), not a bare array — see PagedResponse in
// app/utils/pagination.py. myBills/patientBills below were previously
// typed as Bill[] and rendered via .data?.map(...)/.data?.length, which
// silently showed "no invoices" for every patient because those fields
// don't exist on the envelope object.
interface PagedBill {
  data: Bill[];
  meta: { total: number };
}

const PAYMENT_METHODS = ["cash", "card", "insurance", "bank_transfer", "online"] as const;

// Mirrors VALID_STATUS_TRANSITIONS in backend/app/services/billing.py.
// Kept in sync manually rather than fetched, since it rarely changes and
// a 422/400 from the server is still the source of truth if it drifts.
const NEXT_STATUSES: Record<string, string[]> = {
  unpaid: ["partially_paid", "paid", "cancelled"],
  partially_paid: ["paid", "cancelled"],
  paid: [],
  cancelled: [],
};

function statusBadgeVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "paid") return "default";
  if (status === "cancelled") return "destructive";
  if (status === "partially_paid") return "outline";
  return "secondary";
}

function money(n: number) {
  return `$${n.toFixed(2)}`;
}

function BillingPage() {
  const { hasRole } = useAuth();
  const qc = useQueryClient();
  const isStaff = hasRole(["admin", "receptionist"]);

  const [form, setForm] = useState({ patient_id: "", method: "card" });
  const [lineItems, setLineItems] = useState([{ description: "", quantity: "1", unit_price: "" }]);
  const [taxAmount, setTaxAmount] = useState("0");
  const [discountAmount, setDiscountAmount] = useState("0");
  const [lookupPatientId, setLookupPatientId] = useState("");
  const [activeLookup, setActiveLookup] = useState<string | null>(null);

  function addLineItemRow() {
    setLineItems([...lineItems, { description: "", quantity: "1", unit_price: "" }]);
  }
  function removeLineItemRow(idx: number) {
    setLineItems(lineItems.filter((_, i) => i !== idx));
  }
  function updateLineItemRow(idx: number, patch: Partial<{ description: string; quantity: string; unit_price: string }>) {
    setLineItems(lineItems.map((li, i) => (i === idx ? { ...li, ...patch } : li)));
  }

  const create = useMutation({
    mutationFn: () =>
      api.post<Bill>("/billing/", {
        patient_id: form.patient_id,
        line_items: lineItems
          .filter((li) => li.description.trim())
          .map((li) => ({
            description: li.description,
            quantity: Number(li.quantity) || 1,
            unit_price: Number(li.unit_price) || 0,
          })),
        tax_amount: Number(taxAmount) || 0,
        discount_amount: Number(discountAmount) || 0,
        method: form.method || null,
      }),
    onSuccess: () => {
      toast.success("Invoice created");
      setLineItems([{ description: "", quantity: "1", unit_price: "" }]);
      setTaxAmount("0");
      setDiscountAmount("0");
      qc.invalidateQueries({ queryKey: ["patient-bills", form.patient_id] });
      if (activeLookup === form.patient_id) qc.invalidateQueries({ queryKey: ["patient-bills", activeLookup] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed to create invoice"),
  });

  const updateStatus = useMutation({
    mutationFn: ({ billId, status }: { billId: string; status: string }) =>
      api.put<Bill>(`/billing/${billId}`, { status }),
    onSuccess: () => {
      toast.success("Status updated");
      if (activeLookup) qc.invalidateQueries({ queryKey: ["patient-bills", activeLookup] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Status update failed"),
  });

  // Patients have no reason to know their own Patient UUID, so this hits
  // the dedicated /billing/me route (resolved server-side from the JWT)
  // rather than /billing/{patient_id}.
  const myBills = useQuery({
    queryKey: ["my-bills"],
    queryFn: () => api.get<PagedBill>("/billing/me"),
    enabled: hasRole("patient"),
  });

  const patientBills = useQuery({
    queryKey: ["patient-bills", activeLookup],
    queryFn: () => api.get<PagedBill>(`/billing/${activeLookup}`),
    enabled: isStaff && !!activeLookup,
  });

  async function downloadPdf() {
    const token = getToken();
    const res = await fetch(`${API_BASE}/export/billing/pdf`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!res.ok) { toast.error("Export failed"); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "billing.pdf"; a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Billing" description="Invoices and payments." actions={
        hasRole("admin") ? <Button variant="outline" onClick={downloadPdf}>Export PDF</Button> : null
      } />

      {isStaff && (
        <Card className="max-w-2xl">
          <CardHeader><CardTitle>Create invoice</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="space-y-4">
              <div><Label>Patient ID</Label><Input required value={form.patient_id} onChange={(e) => setForm({ ...form, patient_id: e.target.value })} placeholder="Patient UUID" /></div>

              <div className="space-y-2">
                <Label>Line items</Label>
                {lineItems.map((li, idx) => (
                  <div key={idx} className="flex gap-2">
                    <Input
                      className="flex-[2]"
                      placeholder="Description (e.g. Consultation)"
                      value={li.description}
                      onChange={(e) => updateLineItemRow(idx, { description: e.target.value })}
                    />
                    <Input
                      className="w-20"
                      type="number"
                      min="1"
                      placeholder="Qty"
                      value={li.quantity}
                      onChange={(e) => updateLineItemRow(idx, { quantity: e.target.value })}
                    />
                    <Input
                      className="w-28"
                      type="number"
                      step="0.01"
                      min="0"
                      placeholder="Unit price"
                      value={li.unit_price}
                      onChange={(e) => updateLineItemRow(idx, { unit_price: e.target.value })}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={lineItems.length === 1}
                      onClick={() => removeLineItemRow(idx)}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
                <Button type="button" variant="outline" size="sm" onClick={addLineItemRow}>+ Add line item</Button>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div><Label>Tax</Label><Input type="number" step="0.01" min="0" value={taxAmount} onChange={(e) => setTaxAmount(e.target.value)} /></div>
                <div><Label>Discount</Label><Input type="number" step="0.01" min="0" value={discountAmount} onChange={(e) => setDiscountAmount(e.target.value)} /></div>
                <div>
                  <Label>Method</Label>
                  <Select value={form.method} onValueChange={(v) => setForm({ ...form, method: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {PAYMENT_METHODS.map((m) => <SelectItem key={m} value={m}>{m.replace("_", " ")}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Button type="submit" disabled={create.isPending}>{create.isPending ? "Saving…" : "Create invoice"}</Button>
            </form>
          </CardContent>
        </Card>
      )}

      {isStaff && (
        <Card className="max-w-2xl">
          <CardHeader><CardTitle>Look up invoices</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <form
              onSubmit={(e) => { e.preventDefault(); setActiveLookup(lookupPatientId || null); }}
              className="flex gap-2"
            >
              <Input placeholder="Patient UUID" value={lookupPatientId} onChange={(e) => setLookupPatientId(e.target.value)} />
              <Button type="submit" variant="outline">Look up</Button>
            </form>

            {patientBills.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {patientBills.isError && <p className="text-sm text-destructive">Couldn't load invoices for that patient.</p>}
            {patientBills.data?.data.length === 0 && <p className="text-sm text-muted-foreground">No invoices for this patient.</p>}

            {patientBills.data?.data.map((bill) => (
              <div key={bill.id} className="space-y-2 rounded-md border p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium">{money(bill.amount)}</div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(bill.created_at).toLocaleDateString()}
                      {bill.method ? ` · ${bill.method.replace("_", " ")}` : ""}
                    </div>
                  </div>
                  <Badge variant={statusBadgeVariant(bill.status)}>{bill.status.replace("_", " ")}</Badge>
                </div>

                <div className="space-y-0.5 text-xs text-muted-foreground">
                  {bill.line_items.map((li) => (
                    <div key={li.id} className="flex justify-between">
                      <span>{li.description} {li.quantity > 1 ? `× ${li.quantity}` : ""}</span>
                      <span>{money(li.quantity * li.unit_price)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between border-t pt-1"><span>Subtotal</span><span>{money(bill.subtotal)}</span></div>
                  {bill.discount_amount > 0 && <div className="flex justify-between"><span>Discount</span><span>-{money(bill.discount_amount)}</span></div>}
                  {bill.tax_amount > 0 && <div className="flex justify-between"><span>Tax</span><span>{money(bill.tax_amount)}</span></div>}
                </div>

                {NEXT_STATUSES[bill.status]?.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {/* Mock Stripe "Pay Now" button — triggers checkout session then fires webhook */}
                    {(bill.status === "unpaid" || bill.status === "partially_paid") && (
                      <Button
                        size="sm"
                        variant="default"
                        disabled={updateStatus.isPending}
                        onClick={async () => {
                          try {
                            const session = await api.post<{ checkout_url: string; bill_id: string }>(
                              `/billing/stripe/checkout/${bill.id}`
                            );
                            toast.info(`Mock checkout: ${session.checkout_url}`, { duration: 3000 });
                            // Simulate Stripe webhook after short delay
                            setTimeout(async () => {
                              try {
                                await apiFetch("/billing/stripe/webhook", {
                                  method: "POST",
                                  headers: { "X-Webhook-Secret": STRIPE_WEBHOOK_SECRET },
                                  body: {
                                    type: "checkout.session.completed",
                                    data: { object: { metadata: { bill_id: bill.id } } },
                                  },
                                });
                                toast.success("Payment confirmed (mock Stripe)");
                                qc.invalidateQueries({ queryKey: ["bills"] });
                                qc.invalidateQueries({ queryKey: ["my-bills"] });
                              } catch (e) {
                                toast.error(e instanceof ApiError ? e.message : "Webhook failed");
                              }
                            }, 1200);
                          } catch (e) {
                            toast.error(e instanceof ApiError ? e.message : "Checkout failed");
                          }
                        }}
                      >
                        💳 Pay now (mock)
                      </Button>
                    )}
                    {NEXT_STATUSES[bill.status].map((next) => (
                      <Button
                        key={next}
                        size="sm"
                        variant="outline"
                        disabled={updateStatus.isPending}
                        onClick={() => updateStatus.mutate({ billId: bill.id, status: next })}
                      >
                        Mark {next.replace("_", " ")}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {hasRole("patient") && (
        <Card className="max-w-2xl">
          <CardHeader><CardTitle>Your invoices</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {myBills.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {myBills.isError && <p className="text-sm text-destructive">Couldn't load your invoices.</p>}
            {myBills.data && myBills.data.data.length === 0 && (
              <p className="text-sm text-muted-foreground">No invoices yet.</p>
            )}
            {myBills.data?.data.map((bill) => (
              <div key={bill.id} className="space-y-2 rounded-md border p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium">{money(bill.amount)}</div>
                    <div className="text-xs text-muted-foreground">
                      {new Date(bill.created_at).toLocaleDateString()}
                      {bill.method ? ` · ${bill.method.replace("_", " ")}` : ""}
                    </div>
                  </div>
                  <Badge variant={statusBadgeVariant(bill.status)}>{bill.status.replace("_", " ")}</Badge>
                </div>
                <div className="space-y-0.5 text-xs text-muted-foreground">
                  {bill.line_items.map((li) => (
                    <div key={li.id} className="flex justify-between">
                      <span>{li.description} {li.quantity > 1 ? `× ${li.quantity}` : ""}</span>
                      <span>{money(li.quantity * li.unit_price)}</span>
                    </div>
                  ))}
                </div>
                {(bill.status === "unpaid" || bill.status === "partially_paid") && (
                  <Button
                    size="sm"
                    className="w-full gap-2"
                    onClick={async () => {
                      try {
                        const session = await api.post<{ checkout_url: string; bill_id: string }>(
                          `/billing/stripe/checkout/${bill.id}`
                        );
                        toast.info(`Mock checkout: ${session.checkout_url}`, { duration: 3000 });
                        setTimeout(async () => {
                          try {
                            await apiFetch("/billing/stripe/webhook", {
                              method: "POST",
                              headers: { "X-Webhook-Secret": STRIPE_WEBHOOK_SECRET },
                              body: {
                                type: "checkout.session.completed",
                                data: { object: { metadata: { bill_id: bill.id } } },
                              },
                            });
                            toast.success("Payment confirmed!");
                            qc.invalidateQueries({ queryKey: ["my-bills"] });
                          } catch (e) {
                            toast.error(e instanceof ApiError ? e.message : "Webhook failed");
                          }
                        }, 1200);
                      } catch (e) {
                        toast.error(e instanceof ApiError ? e.message : "Checkout failed");
                      }
                    }}
                  >
                    💳 Pay {money(bill.amount)} now
                  </Button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
