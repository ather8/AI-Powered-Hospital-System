# Step 07 — Patient Portal, Payments, Scheduling & Classifier Fallback

This step addresses items **A**, **C**, **D**, and **E** from the review backlog.

---

## A — Patient-Facing Portal

### What was added

A new route group `_portal.*` gives patients a dedicated, patient-friendly
shell that is separate from the staff sidebar (`_authenticated.*`).

| File | Purpose |
|---|---|
| `frontend/src/routes/_portal.tsx` | Portal layout: top nav with patient-only links, sign-out |
| `frontend/src/routes/_portal.overview.tsx` | Dashboard: next appt, outstanding balance, quick-action cards |
| `frontend/src/routes/_portal.appointments.tsx` | Book, reschedule, cancel appointments with slot picker |
| `frontend/src/routes/_portal.bills.tsx` | View invoices and pay online (Stripe mock) |
| `frontend/src/routes/_portal.records.tsx` | Read-only view of own EMR records |
| `frontend/src/routes/_portal.notifications.tsx` | Read/mark notifications |

### Login redirect

`routes/login.tsx` now reads the JWT role after login and routes:
- `patient` → `/portal/overview`
- all other roles → `/dashboard` (unchanged)

### All data comes from existing backend `/me` endpoints

No new backend routes were needed. The portal uses:
- `GET /appointments/` (patients see only their own appointments)
- `GET /billing/me` (patients see only their own bills)
- `GET /emr/` (patients see only their own records)
- `GET /notifications/` and `PUT /notifications/{id}/read`

---

## D — Doctor Availability / Scheduling Slots

**Already implemented in Step 06** — the backend `GET /appointments/available`
endpoint and the front-end slot picker in `_authenticated.appointments.tsx`
were both complete. The portal's appointment page (`_portal.appointments.tsx`)
uses the same slot-picker pattern with a visual button grid (easier to tap
on mobile) rather than a dropdown.

Conflict detection is enforced at every `POST /appointments/` and
`PUT /appointments/{id}` call via `_assert_no_conflict` in
`routes/appointment.py` (HTTP 409 if a slot is taken).

---

## E — Payment Gateway (Mock Stripe)

### Backend: `backend/app/routes/stripe_mock.py`

Two new endpoints registered under `/billing/stripe`:

```
POST /billing/stripe/checkout/{bill_id}
```
Creates a mock Stripe Checkout session. Returns a `checkout_url` (a mock
Stripe-hosted URL) plus `session_id` and `amount`. In production, replace
the body with `stripe.checkout.Session.create(...)`.

```
POST /billing/stripe/webhook
```
Accepts a Stripe-shaped webhook event body
(`checkout.session.completed`). Marks the bill `paid` and sets
`method = "online"`. Idempotent — calling it twice on an already-paid bill
returns 200 with no state change. Requires an `X-Webhook-Secret` header
matching `STRIPE_WEBHOOK_SECRET` (see `backend/.env.example`) — without it,
401. No real Stripe signature verification (mock); in production replace
the header check with `stripe.Webhook.construct_event` and the endpoint
secret from the Stripe dashboard.

### Frontend integration

- **Patient portal** (`_portal.bills.tsx`): "Pay `$X.XX` now" button →
  calls `/billing/stripe/checkout/{id}`, then simulates Stripe's webhook
  callback 1.2 s later → bill status refreshes to `paid`.
- **Staff billing page** (`_authenticated.billing.tsx`): same "Pay now
  (mock)" button added to unpaid bills in both the staff lookup view and
  the patient's own invoices section.

### Migrating to real Stripe

1. `pip install stripe`
2. Add `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` to `.env`
3. In `stripe_mock.py` replace the checkout body with:
   ```python
   import stripe
   stripe.api_key = settings.stripe_secret_key
   session = stripe.checkout.Session.create(
       payment_method_types=["card"],
       line_items=[{"price_data": {...}, "quantity": 1}],
       mode="payment",
       success_url=f"{settings.frontend_url}/portal/bills?paid=1",
       cancel_url=f"{settings.frontend_url}/portal/bills",
       metadata={"bill_id": str(bill_id)},
   )
   return CheckoutSessionResponse(checkout_url=session.url, ...)
   ```
4. In the webhook handler, replace the `X-Webhook-Secret` header check with
   real signature verification:
   ```python
   event = stripe.Webhook.construct_event(
       payload, sig_header, settings.stripe_webhook_secret
   )
   ```
5. Remove the `setTimeout` simulation *and* the `X-Webhook-Secret` header
   from the frontend (`_portal.bills.tsx`, `_authenticated.billing.tsx`) —
   real Stripe calls `/billing/stripe/webhook` directly, server-to-server,
   so the frontend should never see or send the webhook secret at all.

---

## C — Symptom Classifier Honest Fallback

### Problem

`classify_symptom` raises `RuntimeError` when the ClinicalBERT model is
not installed (the default state — no trained model ships with this repo).
Previously, this propagated as an opaque 500 that masked the LLM reply the
chatbot *had* already generated.

### Fix

`services/langchain_chatbot.py` now wraps `classify_symptom` in a
`try/except RuntimeError`. On failure it returns:

```json
{
  "conversation_reply": "...",
  "disease": null,
  "severity": null,
  "department": null,
  "confidence": null,
  "classification_available": false,
  "disclaimer": "..."
}
```

The conversational LLM reply is **never suppressed** — only the
classification badges are absent.

### Frontend (`_authenticated.chatbot.tsx`)

When `classification_available` is `false`, the bot message shows:

> ⚠️ Symptom classification unavailable — no trained model is installed.
> The conversational reply above is still active. Please consult a doctor
> for any diagnosis.

When the model *is* installed and working, the existing disease / severity
/ confidence badges render as before.

### Installing a real model

Run `python backend/app/services/train_clinicalbert.py` (requires a labelled
dataset) to produce `backend/models/clinicalbert-disease/`. Once the
directory exists, the classifier loads on first call and
`classification_available` will be `true`.

---

## Summary of files changed

### Backend
| File | Change |
|---|---|
| `app/routes/stripe_mock.py` | **New** — mock Stripe checkout + webhook |
| `app/main.py` | Register `stripe_mock` router |
| `app/services/langchain_chatbot.py` | Honest fallback for classifier; `classification_available` field |

### Frontend
| File | Change |
|---|---|
| `src/routes/_portal.tsx` | **New** — patient portal layout |
| `src/routes/_portal.overview.tsx` | **New** — portal home / stats |
| `src/routes/_portal.appointments.tsx` | **New** — patient appointment booking & management |
| `src/routes/_portal.bills.tsx` | **New** — patient invoices + Pay Now (mock Stripe) |
| `src/routes/_portal.records.tsx` | **New** — read-only EMR view |
| `src/routes/_portal.notifications.tsx` | **New** — patient notifications |
| `src/routes/login.tsx` | Role-aware redirect (patients → portal) |
| `src/routes/_authenticated.billing.tsx` | Pay Now (mock) button on unpaid bills |
| `src/routes/_authenticated.chatbot.tsx` | Display `classification_available` fallback notice |
| `src/routeTree.gen.ts` | Register all `_portal.*` routes |
