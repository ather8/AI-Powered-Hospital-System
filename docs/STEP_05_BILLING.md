# Step 5: Billing overhaul

Addresses item 5 from the original review ("Billing is very thin").

## What changed

### Data model
- New `billing_line_items` table: `description`, `quantity`, `unit_price`,
  FK'd to `billing`. An invoice is now a list of charges, not one opaque
  number.
- `billing` gained `subtotal`, `tax_amount`, `discount_amount`. `amount` is
  kept as the existing column but now means the *computed* grand total
  (`subtotal - discount + tax`), recalculated server-side any time line
  items, tax, or discount change (`app/services/billing.py:recalculate_totals`).
- `status` is now NOT NULL with an enforced transition graph instead of an
  arbitrary string:
  - `unpaid → partially_paid → paid`
  - `unpaid → cancelled`, `partially_paid → cancelled`
  - `paid` and `cancelled` are terminal.
- `method` is constrained to `cash | card | insurance | bank_transfer | online`
  at the Pydantic schema layer (consistent with how `Appointment.status` is
  validated at the service layer rather than via a DB-level enum/CHECK).
- Migration `0006_billing_line_items` backfills every pre-existing bill with
  one synthetic line item equal to its old `amount`, so historical invoices
  stay internally consistent under the new model.

### Bugfix: broken migration chain
`0005_appointment_department.py` had `down_revision = "0004"`, but
`0004_doctor_user_link.py`'s actual revision id is `"0004_doctor_user_link"`.
This meant `alembic upgrade head` could never resolve revision `"0004"` and
would fail outright — so the RBAC/department migration from the previous
step had never actually been applicable in a fresh environment.
Fixed by pointing `0005` at the correct parent revision id.

### Bugfix: dead analytics filter
`services/analytics.py` filtered `Billing.status == "pending"` for
`pending_invoices` — `"pending"` was never a real status value (the
vocabulary is `unpaid` / `partially_paid` / `paid` / `cancelled`), so this
metric had always silently returned 0. Now filters on
`status IN (unpaid, partially_paid)` and adds a `cancelled_invoices` count.

### API
- `POST /billing/` now takes `line_items` (required, ≥1), `tax_amount`,
  `discount_amount`, `method` — no more client-supplied `amount`.
- `PUT /billing/{bill_id}` validates status transitions (400 on an invalid
  edge, 422 on an unknown status) and recomputes totals if tax/discount change.
- New `POST /billing/{bill_id}/line-items` and
  `DELETE /billing/{bill_id}/line-items/{item_id}` — both recompute totals;
  both reject mutation once a bill is `paid` or `cancelled`; removing the
  last remaining line item is rejected (delete the bill instead).
- `GET /export/billing/pdf` now reports the subtotal/discount/tax breakdown
  instead of just the final amount.

### Frontend
- Billing page: dynamic line-item rows (add/remove), tax/discount inputs, a
  payment-method `<Select>` constrained to the same vocabulary as the
  backend, and per-invoice "Mark paid / partially paid / cancelled" buttons
  driven by the same transition graph as the server.
- Staff (admin/receptionist) previously had no way to *view* existing bills,
  only create them — added a "look up invoices by patient ID" panel,
  consistent with the existing patient-lookup-by-ID pattern (no list/
  pagination endpoints exist yet — that's tracked separately, item 14).

### Tests
New `app/tests/test_billing.py` (31 tests): pure unit tests for totals
calculation and status-transition validation, plus route-level integration
tests (create with line items, reject empty/unknown method, status
transition enforcement, line-item add/remove + recompute, `/billing/me`
ownership scoping). Run against an in-memory SQLite DB with `StaticPool`
(required so the FastAPI TestClient's worker-thread requests see the same
in-memory database as the test setup — confirmed by reproducing the bug).

Also discovered and worked around: `test_rbac.py`'s `_patch_auth` helper
(`unittest.mock.patch` on `get_current_user`) does not actually take effect
against routes using `require_roles(...)` as a function-default dependency
— FastAPI captures the real function object at route-registration time, so
patching the module attribute afterward changes nothing. This is a
pre-existing issue (several `test_rbac.py` assertions fail with 401 instead
of 403 today) and out of scope to fix here, but `test_billing.py` avoids it
by using `app.dependency_overrides` instead.

## Verified
- All 6 Alembic migrations applied cleanly against a real Postgres 16
  instance, including the previously-broken 0004→0005 link.
- Backfill produces correct `subtotal`/line-item rows for pre-existing data.
- 31/31 new billing tests pass; ran the full existing suite afterward and
  confirmed all pre-existing failures are unrelated to this change (SQLite
  UUID handling in `test_notifications.py`, missing fixture in
  `test_services.py`, the `test_rbac.py` mock.patch issue above, and two
  `test_appointment_conflicts.py` edge cases).
- Frontend type-checks (`tsc --noEmit`) and builds (`vite build`) cleanly;
  the one pre-existing TS error (`auth.callback.tsx`) is unrelated.

## Known follow-ups (not done here, flagged for a future step)
- No payment gateway integration (still a stub `method` field, just
  constrained now instead of freetext).
- `test_rbac.py`'s broken auth-mocking pattern should be fixed so its
  "forbidden role" assertions actually test what they claim to.
- Patient/EMR/Doctor list endpoints still have no pagination (item 14) —
  the new "look up invoices by patient ID" panel inherits that limitation.

## Incidental fix: stale routeTree.gen.ts
Running the frontend build regenerated `src/routeTree.gen.ts`, which was
missing the `/auth/callback` route registration even though
`src/routes/auth.callback.tsx` exists on disk — this was the cause of the
one pre-existing TypeScript error (`auth.callback.tsx(18,38): ... not
assignable to 'keyof FileRoutesByPath'`). The regenerated file is included
in this delivery; `tsc --noEmit` is now clean.
