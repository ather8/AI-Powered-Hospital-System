# Step 6 — Pagination on List Endpoints + Chatbot Conversation Memory

## What changed

### Backend

#### `app/utils/pagination.py` (new)
Central pagination module — one place for all list endpoints to import from.

- **`PageParams`** — FastAPI dependency that reads `skip` (≥ 0) and `limit` (1–200, default 20) from query params. The 200-item hard cap prevents full-table scans via the API.
- **`PageMeta`** — Pydantic model with `total`, `skip`, `limit`, `has_next`, `has_prev`.
- **`PagedResponse[T]`** — Generic envelope. All paginated list endpoints return `{ "data": [...], "meta": {...} }`.

#### Routes updated with pagination
| Route | Before | After |
|-------|--------|-------|
| `GET /patients/` | `list[PatientResponse]` | `PagedResponse[PatientResponse]` |
| `GET /doctors/` | `list[DoctorResponse]` | `PagedResponse[DoctorResponse]` |
| `GET /appointments/` | `list[AppointmentResponse]` | `PagedResponse[AppointmentResponse]` |
| `GET /audit-logs/` | `list[dict]` (unbounded) | `PagedResponse[dict]` |
| `GET /billing/me` | `list[BillingResponse]` | `PagedResponse[BillingResponse]` |
| `GET /billing/{patient_id}` | `list[BillingResponse]` | `PagedResponse[BillingResponse]` |

All paginated queries include `.order_by()` so results are stable across pages.

#### `app/services/langchain_chatbot.py` (rewritten)
Added **session-keyed conversation memory** to the triage chatbot.

Key design:
- In-process `dict` store keyed by `session_id` (UUID string). Lightweight, no Redis dependency needed for single-worker deployments.
- Sessions expire after `CHATBOT_SESSION_TTL_MINUTES` (default: 30) minutes of inactivity, pruned lazily on each request.
- History is capped at `CHATBOT_MAX_HISTORY_TURNS` (default: 20) turn-pairs to stay within model context limits.
- Each turn stores `{"role": "user"|"assistant", "content": str}` dicts — the minimal format the OpenAI-compatible endpoint understands.
- On each request, full history is assembled as `[SystemMessage, ...HumanMessage/AIMessage pairs..., HumanMessage(current)]` before calling the LLM.
- Both env vars are overridable without code changes.

New public function: `clear_session(session_id)` — removes a session (called by the "New Conversation" endpoint).

#### `app/models/patient_input.py`
Added `session_id: Optional[str] = None` field.

#### `app/routes/chatbot.py`
- If `session_id` is not supplied, the server mints one (UUID4) and echoes it back.
- New `DELETE /chatbot/conversation/{session_id}` endpoint resets history.

### Frontend

#### `src/hooks/use-pagination.ts` (new)
`usePagination(limit?)` hook — returns `{ skip, limit, next, prev, reset }`. Pair with a `useQuery` whose key includes `[skip, limit]`.

#### Pages updated
- **`patients.tsx`** — Staff roles now see a paginated table of all patients with Previous/Next controls and a `X–Y of N` counter.
- **`audit-logs.tsx`** — Table is now paginated; total count shown in the header.
- **`chatbot.tsx`** — Maintains `sessionId` state. First response auto-sets it; subsequent turns include it. "New Conversation" button calls `DELETE /chatbot/conversation/{id}` and resets local state. Bot messages now show triage badges (disease, severity, department, confidence). Auto-scroll to latest message.

### Tests

#### `app/tests/test_pagination.py` (new)
- Unit: `PagedResponse.create` — meta flags, data passthrough
- Integration: `/patients/` and `/audit-logs/` return paged envelope; skip works; limit > 200 → 422

#### `app/tests/test_chatbot_memory.py` (new)
- No AI API calls — LLM chain patched with a message-counter stub
- Session creation, history accumulation, turn-growth, `clear_session`, trim at max turns, stateless (no session_id) mode

## Usage

```bash
# List patients, page 2 (items 21–40)
GET /patients/?skip=20&limit=20

# List patients, smaller pages
GET /patients/?skip=0&limit=5

# Chatbot — turn 1 (no session_id → server creates one)
POST /chatbot/conversation
{"name": "Alice", "age": 32, "symptoms": "chest pain", "session_id": null}
→ {"conversation_reply": "...", "session_id": "uuid-here", ...}

# Chatbot — turn 2 (reuse session_id)
POST /chatbot/conversation
{"name": "Alice", "age": 32, "symptoms": "sharp, since this morning", "session_id": "uuid-here"}
→ {"conversation_reply": "Does the pain radiate to your arm?", ...}

# Reset conversation
DELETE /chatbot/conversation/uuid-here
→ {"message": "Conversation cleared", "session_id": "uuid-here"}
```

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `CHATBOT_SESSION_TTL_MINUTES` | `30` | Minutes of inactivity before session expires |
| `CHATBOT_MAX_HISTORY_TURNS` | `20` | Max user+assistant pairs stored per session |
| `RATE_CHATBOT` | `20/minute` | Per-user chatbot rate limit |
