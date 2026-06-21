# AI-Powered Hospital Management System

A full-stack hospital platform with AI-assisted triage, clinical search, document OCR, and a patient-facing portal. Built with **FastAPI** (Python) + **React** (TypeScript) + **PostgreSQL**.

---

## Table of contents

1. [Feature overview](#feature-overview)
2. [Screenshots](#screenshots)
3. [Quick start — Docker Compose](#quick-start--docker-compose)
4. [Database setup](#database-setup)
5. [Environment variables](#environment-variables)
6. [AI features setup](#ai-features-setup)
7. [Local development (without Docker)](#local-development-without-docker)
8. [Production deployment](#production-deployment)
9. [Project structure](#project-structure)
10. [Running tests](#running-tests)
11. [Architecture notes](#architecture-notes)

---

## Feature overview

| Area | What's included |
|------|----------------|
| **Auth** | JWT login, registration, Google OAuth, RBAC (admin / doctor / nurse / receptionist / patient) |
| **Patient portal** | Appointments, bills, medical records, notifications — patient-facing shell |
| **Patients** | CRUD, search, pagination, patient-scoped `/me` endpoints |
| **Doctors** | CRUD, linked user accounts, department assignment |
| **Appointments** | Scheduling with conflict detection, department field, paginated list |
| **EMR** | Electronic medical records with audit trail |
| **Billing** | Line-item invoices, status transitions (`unpaid → paid`), mock Stripe checkout |
| **AI Triage Chatbot** | Multi-turn conversation with session memory (30-min TTL), symptom classification, department routing |
| **AI Summary** | Paste a medical report → structured summary |
| **AI Notes** | Free-text dictation → structured clinical note |
| **AI Clinical Search** | RAG pipeline over medical guidelines (FAISS + LLM) |
| **OCR** | Upload a scanned document → extracted text → optional EMR/summary |
| **Notifications** | In-app notification feed with unread badge |
| **Audit Logs** | Tamper-evident log of every write action |
| **Analytics** | Admin-only platform analytics |
| **Export** | CSV export of patients / appointments |

---

---

## Screenshots

### Landing page

| Hero | Features |
|---|---|
| ![Landing hero](docs/screenshots/landing-hero.png) | ![Landing features](docs/screenshots/landing-features.png) |

### Auth

| Sign in | Create account |
|---|---|
| ![Sign in](docs/screenshots/auth-login.png) | ![Create account](docs/screenshots/auth-register.png) |

### Patient portal

| Overview | Appointments |
|---|---|
| ![Patient portal overview](docs/screenshots/patient-portal-overview.png) | ![Patient appointments](docs/screenshots/patient-appointments.png) |

**AI Symptom Checker** — multi-turn triage chatbot with session memory:

![AI Symptom Checker](docs/screenshots/ai-symptom-checker.png)

### Staff workspace (admin / doctor / nurse / receptionist)

| Dashboard | Patients |
|---|---|
| ![Staff dashboard](docs/screenshots/staff-dashboard.png) | ![Staff patients](docs/screenshots/staff-patients.png) |

| Appointments | Billing |
|---|---|
| ![Staff appointments](docs/screenshots/staff-appointments.png) | ![Staff billing](docs/screenshots/staff-billing.png) |

---

## Quick start — Docker Compose

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 4.x (includes Docker Compose v2)
- Git

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/your-username/ai-hospital-system.git
cd ai-hospital-system

# 2. Create your environment file
cp backend/.env.example backend/.env
#    Open backend/.env and fill in at minimum:
#      SECRET_KEY   — generate with: python -c "import secrets; print(secrets.token_hex(32))"
#      JWT_SECRET   — generate a second random hex string the same way
#      GEMINI_API_KEY (or OPENAI_API_KEY) — for AI features

# 3. Start all services (PostgreSQL + Redis + backend + frontend)
docker compose up --build
```

First run takes 2–4 minutes to pull images and install dependencies. On subsequent runs it starts in seconds.

| Service | URL |
|---------|-----|
| Frontend (Vite dev) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |

> **First-time login:** Register a new account at http://localhost:5173. The first user you register can be manually promoted to admin by updating their `role` column in the database (`UPDATE users SET role = 'admin' WHERE email = 'you@example.com';`).

### Useful commands

```bash
# Run in background
docker compose up -d --build

# View live logs
docker compose logs -f backend

# Apply any new database migrations
docker compose exec backend alembic upgrade head

# Open a psql shell
docker compose exec db psql -U hospital -d hospital

# Stop everything (keeps data)
docker compose down

# Stop and wipe the database
docker compose down -v
```

---

## Database setup

The project supports two database configurations:

### Option A — Local PostgreSQL via Docker (default, recommended for development)

No setup required. `docker compose up` automatically starts a PostgreSQL 16 container and runs migrations on every boot. Data is persisted in the `pgdata` Docker volume.

Connection string (pre-filled in `backend/.env` when using Docker):
```
DATABASE_URL=postgresql://hospital:hospital@db:5432/hospital
```

### Option B — Supabase (recommended for cloud / team development)

[Supabase](https://supabase.com) provides a managed PostgreSQL database with a generous free tier.

1. Go to [supabase.com](https://supabase.com) → **New project**.
2. Choose a region close to your users.
3. Once the project is ready, go to **Project Settings → Database → Connection string** and select **URI**.
4. Copy the connection string — it looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres
   ```
5. Set it in `backend/.env`:
   ```
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres
   ```
6. Run migrations once to create the schema:
   ```bash
   # With Docker running:
   docker compose exec backend alembic upgrade head

   # Or locally (with venv activated):
   cd backend && alembic upgrade head
   ```

> **Note:** When using Supabase you no longer need the `db` Docker service. You can comment it out of `docker-compose.yml` and remove the `db` condition from `backend.depends_on`.

### Database migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Create a new migration after changing a model
alembic revision --autogenerate -m "describe your change"

# View migration history
alembic history
```

---

## Environment variables

Copy `backend/.env.example` to `backend/.env` and fill in the values. All variables are documented in the example file.

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Cookie/session signing key — generate a random hex string |
| `JWT_SECRET` | Yes | JWT token signing key — generate a separate random hex string |
| `DATABASE_URL` | Yes | PostgreSQL connection string (see [Database setup](#database-setup)) |
| `REDIS_URL` | Yes | Redis connection string — `redis://redis:6379/0` with Docker |
| `GEMINI_API_KEY` | One of these | Free tier at [aistudio.google.com](https://aistudio.google.com/apikey) |
| `OPENAI_API_KEY` | One of these | Paid OpenAI account |
| `GOOGLE_CLIENT_ID` | Optional | Google OAuth — leave blank to disable |
| `GOOGLE_CLIENT_SECRET` | Optional | Google OAuth |
| `FRONTEND_URL` | Optional | Used for CORS — defaults to `http://localhost:5173` |
| `STRIPE_WEBHOOK_SECRET` | Optional | Mock Stripe webhook secret — a default dev value is provided |

> **Security:** Set `ENV=production` in your environment to make the app **refuse to start** if `SECRET_KEY` or `JWT_SECRET` are missing, rather than just warning.

> **Never commit `backend/.env` to Git.** It is listed in `.gitignore`. Only `backend/.env.example` (which contains no real secrets) should be committed.

---

## AI features setup

### Provider selection

Set **one** AI provider key in `backend/.env`:

```bash
# Recommended — Gemini has a free tier
GEMINI_API_KEY=your-key-from-aistudio.google.com

# Alternative — requires a paid OpenAI account
OPENAI_API_KEY=sk-...
```

The app auto-detects which key is present. All AI routes return `503 Service Unavailable` if neither key is set.

### Clinical search (FAISS vector index)

The AI Clinical Search feature requires a pre-built vector index. Build it once after starting the backend:

```bash
# With Docker running:
docker compose exec backend python build_faiss_index.py

# Locally:
cd backend && python build_faiss_index.py
```

This creates `backend/medical_guidelines_index/`. The FAISS index is excluded from Git by `.gitignore` (it can be several hundred MB). Copy it to your server manually, or rebuild it there.

If the index is missing, clinical search returns `{ "status": "disabled" }` instead of crashing.

### Symptom classification (ClinicalBERT — optional)

The chatbot can classify symptoms into a likely disease and department using a fine-tuned ClinicalBERT model. This is **not enabled by default** — no trained model ships in the repo.

To enable it:

1. Get a labeled dataset (Kaggle: "disease symptom prediction dataset") with a symptom text column and a disease label column.
2. Install training extras:
   ```bash
   pip install datasets accelerate
   ```
3. Train the model:
   ```bash
   cd backend
   python -m app.services.train_clinicalbert \
       --csv path/to/dataset.csv \
       --text-col symptoms \
       --label-col disease
   ```
4. Restart the backend — the model loads from `./models/clinicalbert-disease` on first use.

Without a trained model the chatbot still works; it just returns `classification_available: false`.

---

## Local development (without Docker)

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL to a local Postgres instance

# Apply database migrations
alembic upgrade head

# Start the dev server (auto-reloads on file changes)
uvicorn app.main:app --reload
```

API available at http://localhost:8000 — interactive docs at http://localhost:8000/docs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend available at http://localhost:5173.

The `VITE_API_BASE_URL` environment variable controls which backend the frontend talks to. It defaults to `http://localhost:8000`.

---

## Production deployment

### Docker Compose (single server)

Build a compiled, optimised bundle served via nginx:

```bash
# Build and start the production frontend (port 80) alongside the backend
docker compose --profile prod up --build -d
```

This uses `frontend/Dockerfile` which runs `npm run build` and serves the output via nginx. The dev `frontend` service (port 5173) is not started.

Set `VITE_API_BASE_URL` in the build args to your public backend URL:

```bash
VITE_API_BASE_URL=https://api.yourdomain.com docker compose --profile prod up --build -d
```

### Checklist before going live

- [ ] Generate new `SECRET_KEY` and `JWT_SECRET` values (never reuse dev values)
- [ ] Set `ENV=production` in `backend/.env` so the app refuses to start on missing secrets
- [ ] Point `DATABASE_URL` to a managed database (Supabase, RDS, etc.)
- [ ] Set `FRONTEND_URL` to your actual domain for CORS
- [ ] Set `GOOGLE_REDIRECT_URI` to your production callback URL
- [ ] Put a reverse proxy (nginx, Caddy, Traefik) in front and terminate TLS there
- [ ] Set `VITE_API_BASE_URL` to your public API URL at build time

---

## Project structure

```
ai-hospital-system/
├── docker-compose.yml          ← Orchestrates db + redis + backend + frontend
├── README.md
├── backend/
│   ├── .env.example            ← Copy to .env and fill in secrets (never commit .env)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── build_faiss_index.py    ← Pre-build FAISS index for clinical search
│   ├── alembic/                ← Database migration history
│   │   └── versions/           ← One file per migration
│   └── app/
│       ├── config.py           ← Env var loading + startup validation
│       ├── main.py             ← FastAPI app factory, middleware, routers
│       ├── models/             ← SQLAlchemy ORM models
│       ├── schemas/            ← Pydantic request/response schemas
│       ├── routes/             ← API route handlers
│       ├── services/           ← Business logic and AI service layer
│       └── utils/              ← JWT, RBAC, rate limiting, pagination
└── frontend/
    ├── Dockerfile              ← Production build (nginx)
    └── src/
        ├── routes/             ← Page components (TanStack Router file-based)
        ├── components/         ← Shared UI components + error boundaries
        └── lib/                ← API client, auth context, route guards
```

---

## Running tests

**Backend (pytest):**
```bash
cd backend
pytest -v
```

**Frontend (Vitest + React Testing Library):**
```bash
cd frontend
npm test
```

---

## Architecture notes

- **Rate limiting:** AI endpoints are rate-limited per authenticated user via `slowapi`. Defaults: 20 req/min for the chatbot, 10/min for other AI routes. Override via env vars (`RATE_CHATBOT`, `RATE_AI_SUMMARY`, etc.).
- **Chatbot session memory:** Conversation history is stored in-process with a 30-minute TTL. For multi-worker deployments, configure `REDIS_URL` and update `langchain_chatbot.py` to use Redis-backed memory.
- **Database migrations:** Alembic handles all schema changes. The backend's Docker entrypoint runs `alembic upgrade head` automatically on every start, so migrations are always applied before the server comes up.
- **RBAC:** Every sensitive route is guarded by `require_roles([...])`. Hierarchy: `admin > doctor/nurse > receptionist > patient`.
- **Secrets enforcement:** Set `ENV=production` to raise at startup on missing `SECRET_KEY`/`JWT_SECRET` rather than just warning.
