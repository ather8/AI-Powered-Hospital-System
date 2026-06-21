/**
 * Patient Portal — Bills & Payments
 * Shows the patient's own bills with a "Pay Now" button that triggers
 * the mock Stripe checkout flow (feature E).
 */
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch, api, ApiError, STRIPE_WEBHOOK_SECRET } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CreditCard, CheckCircle2, ExternalLink } from "lucide-react";

export const Route = createFileRoute("/portal/_portal/bills")({
  head: () => ({ meta: [{ title: "My Bills — Aetheris" }] }),
  component: PortalBills,
});

interface LineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: number;
}

interface Bill {
  id: string;
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  amount: number;
  status: string;
  method: string | null;
  created_at: string;
  line_items: LineItem[];
}

interface PagedBill {
  data: Bill[];
  meta: { total: number };
}

interface CheckoutResponse {
  checkout_url: string;
  session_id: string;
  bill_id: string;
  amount: number;
}

function statusBadge(s: string): "default" | "secondary" | "destructive" | "outline" {
  if (s === "paid") return "default";
  if (s === "cancelled") return "destructive";
  if (s === "partially_paid") return "outline";
  return "secondary";
}

function money(n: number) {
  return `$${n.toFixed(2)}`;
}

function BillCard({ bill, onPaid }: { bill: Bill; onPaid: () => void }) {
  const checkout = useMutation({
    mutationFn: () =>
      api.post<CheckoutResponse>(`/billing/stripe/checkout/${bill.id}`),
    onSuccess: (data) => {
      // In production we'd do window.location.href = data.checkout_url
      // For the mock, we fire the webhook immediately to simulate payment.
      toast.info(
        `Redirecting to payment…\n(Mock: ${data.checkout_url})`,
        { duration: 3000 }
      );
      // Simulate Stripe calling our webhook ~1 s later (mock flow).
      setTimeout(async () => {
        try {
          await apiFetch("/billing/stripe/webhook", {
            method: "POST",
            headers: { "X-Webhook-Secret": STRIPE_WEBHOOK_SECRET },
            body: {
              type: "checkout.session.completed",
              data: {
                object: {
                  metadata: { bill_id: bill.id },
                },
              },
            },
          });
          toast.success("Payment confirmed!");
          onPaid();
        } catch (e) {
          toast.error(
            e instanceof ApiError ? e.message : "Payment confirmation failed"
          );
        }
      }, 1200);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Could not start payment"),
  });

  const isPending = bill.status === "unpaid" || bill.status === "partially_paid";

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            Invoice — {new Date(bill.created_at).toLocaleDateString([], {
              year: "numeric",
              month: "short",
              day: "numeric",
            })}
          </CardTitle>
          <Badge variant={statusBadge(bill.status)}>{bill.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Line items */}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-muted-foreground">
              <th className="pb-1 text-left font-normal">Description</th>
              <th className="pb-1 text-right font-normal">Qty</th>
              <th className="pb-1 text-right font-normal">Unit</th>
              <th className="pb-1 text-right font-normal">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {bill.line_items.map((li) => (
              <tr key={li.id}>
                <td className="py-1">{li.description}</td>
                <td className="py-1 text-right">{li.quantity}</td>
                <td className="py-1 text-right">{money(li.unit_price)}</td>
                <td className="py-1 text-right">
                  {money(li.quantity * li.unit_price)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Totals */}
        <div className="space-y-1 border-t pt-2 text-sm">
          <div className="flex justify-between text-muted-foreground">
            <span>Subtotal</span>
            <span>{money(bill.subtotal)}</span>
          </div>
          {bill.discount_amount > 0 && (
            <div className="flex justify-between text-muted-foreground">
              <span>Discount</span>
              <span>-{money(bill.discount_amount)}</span>
            </div>
          )}
          {bill.tax_amount > 0 && (
            <div className="flex justify-between text-muted-foreground">
              <span>Tax</span>
              <span>{money(bill.tax_amount)}</span>
            </div>
          )}
          <div className="flex justify-between font-semibold">
            <span>Total</span>
            <span>{money(bill.amount)}</span>
          </div>
          {bill.method && (
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Payment method</span>
              <span>{bill.method}</span>
            </div>
          )}
        </div>

        {/* Pay button (only for payable bills) */}
        {isPending && (
          <Button
            className="w-full gap-2"
            disabled={checkout.isPending}
            onClick={() => checkout.mutate()}
          >
            {checkout.isPending ? (
              "Processing…"
            ) : (
              <>
                <CreditCard className="h-4 w-4" />
                Pay {money(bill.amount)} now
              </>
            )}
          </Button>
        )}
        {bill.status === "paid" && (
          <div className="flex items-center gap-1.5 text-sm text-green-600 dark:text-green-400">
            <CheckCircle2 className="h-4 w-4" />
            Paid
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PortalBills() {
  const qc = useQueryClient();

  const billsQ = useQuery({
    queryKey: ["portal-bills"],
    queryFn: () => api.get<PagedBill>("/billing/me"),
  });

  const bills = billsQ.data?.data ?? [];
  const unpaid = bills.filter(
    (b) => b.status === "unpaid" || b.status === "partially_paid"
  );
  const paid = bills.filter(
    (b) => b.status === "paid" || b.status === "cancelled"
  );

  function refetch() {
    qc.invalidateQueries({ queryKey: ["portal-bills"] });
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Bills & Payments</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          View your invoices and pay outstanding balances online.
        </p>
      </div>

      {billsQ.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      )}

      {!billsQ.isLoading && bills.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            <CreditCard className="mx-auto mb-2 h-8 w-8 opacity-30" />
            No invoices on file yet — bills will appear here after your first visit.
          </CardContent>
        </Card>
      )}

      {unpaid.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-base font-semibold">Outstanding balances</h2>
          {unpaid.map((b) => (
            <BillCard key={b.id} bill={b} onPaid={refetch} />
          ))}
        </section>
      )}

      {paid.length > 0 && (
        <section className="space-y-4">
          <h2 className="text-base font-semibold text-muted-foreground">
            Past invoices
          </h2>
          {paid.map((b) => (
            <BillCard key={b.id} bill={b} onPaid={refetch} />
          ))}
        </section>
      )}

      <p className="text-xs text-muted-foreground">
        Payments are processed securely. Contact the billing department if
        you have any questions about your invoice.
      </p>
    </div>
  );
}
