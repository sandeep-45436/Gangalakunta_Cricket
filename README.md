# Cricket Highlights

Mobile recording · Ball-by-ball scoring · Automatic player-wise clips

A web-first platform for recording cricket matches, entering ball-by-ball scores, and automatically generating player-specific highlight clips. Built on InsForge (PostgreSQL, Auth, Storage).

---

## Architecture

```
Browser (React + Vite) ──► FastAPI backend ──► InsForge (DB + Auth + Storage)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full component diagram.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | ≥ 20 | https://nodejs.org |
| Python | 3.11 | https://python.org |
| npx | bundled with npm | — |

---

## Local Setup

### 1. Clone and link InsForge

```bash
# The project is already linked. Verify:
npx -y @insforge/cli current
```

If you're setting up on a new machine:

```bash
npx @insforge/cli login --user-api-key <your-user-api-key>
npx -y @insforge/cli link --project-id fb63c740-6597-4b54-b93a-96c2944163c7
```

### 2. Configure environment variables

```bash
# Backend
cp .env.example services/api/.env
# Edit services/api/.env — fill in INSFORGE_URL, INSFORGE_ANON_KEY, INSFORGE_API_KEY
# Get values with:
npx -y @insforge/cli secrets get ANON_KEY
npx -y @insforge/cli secrets get API_KEY

# Frontend
cp .env.example apps/web/.env
# Edit apps/web/.env — fill in VITE_INSFORGE_URL, VITE_INSFORGE_ANON_KEY
```

### 3. Run database migrations

```bash
npx -y @insforge/cli db migrations up --all
```

### 4. Start the FastAPI backend

```bash
cd services/api
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend is now running at http://localhost:8000  
API docs at http://localhost:8000/docs

### 5. Start the frontend

```bash
cd apps/web
npm install
npm run dev
```

Frontend is now running at http://localhost:5173

Open the browser — you'll see the connectivity dashboard showing API, Database, and Storage status.

---

## Running Tests

### Backend (Python / pytest)

```bash
cd services/api
.venv\Scripts\activate
pytest tests/ -v
```

Expected: **7 passed**

### Frontend (Vitest)

```bash
cd apps/web
npm run test
```

Expected: **3 passed**

---

## Database Migrations

InsForge uses its own SQL-file migration system:

```bash
# View applied migrations
npx -y @insforge/cli db migrations list

# Create a new migration
npx -y @insforge/cli db migrations new <migration-name>

# Apply all pending migrations
npx -y @insforge/cli db migrations up --all
```

Migrations live in `migrations/` at the project root.  
**Do not use Alembic** — this project uses InsForge CLI migrations.

---

## Storage

The `cricket-videos` bucket is created (private) in InsForge Storage.  
Video uploads (Phase 3+) will use the `@insforge/sdk` storage module.

---

## Project Structure

```
cricket-highlights/
├── apps/web/              ← React + Vite + TypeScript frontend
├── services/
│   ├── api/               ← FastAPI backend
│   └── video-worker/      ← Phase 4 FFmpeg worker (placeholder)
├── migrations/            ← InsForge SQL migrations
├── docs/                  ← Architecture, API, PRD
├── AGENTS.md              ← InsForge agent skills config
├── .env.example           ← Environment variable template
└── README.md
```

---

## Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 0 | ✅ Done | Foundation, health checks, auth plumbing, storage bucket |
| 1 | Next | Teams, squads, players, matches, playing XI |
| 2 | — | Ball-by-ball scoring engine |
| 3 | — | Video recording with delivery timestamp markers |
| 4 | — | Automatic clip extraction and player assignment |
| 5 | — | Milestone animations (50, 100, 150, 200) |
| 6 | — | Production readiness, search, archival |

---

## Known Limitations (Phase 0)

- **JWT signature verification is partial**: In `app/core/auth.py`, Phase 0 skips cryptographic signature verification (`verify_signature: False`). Full verification using the InsForge `JWT_SECRET` will be added in Phase 1 when the user table exists.
- **No domain tables yet**: The database has the migration baseline but no application tables. Phase 1 adds teams, players, matches, etc.
- **No recording workflow**: Video recording and marker placement are Phase 3.
- **No clip extraction**: FFmpeg worker is a placeholder until Phase 4.

---

## Troubleshooting

**`INSFORGE_URL` or `INSFORGE_ANON_KEY` missing**  
Run `npx -y @insforge/cli secrets get ANON_KEY` and add the value to your `.env` file.

**`/health/db` returns 503**  
The InsForge API key may be missing or wrong. Check `INSFORGE_API_KEY` in `services/api/.env`.

**Frontend shows "error" for all services**  
Make sure the FastAPI backend is running on port 8000 before starting the frontend.

**`npx @insforge/cli` prompts "Ok to proceed?"**  
Always use `npx -y @insforge/cli` (with the `-y` flag) to skip the install confirmation.
