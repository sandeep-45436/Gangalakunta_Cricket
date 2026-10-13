# Architecture — Cricket Highlights

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Browser                                                     │
│  React + Vite + TypeScript (apps/web)                        │
│                                                              │
│  ┌────────────────────┐   ┌────────────────────────────┐    │
│  │  InsForge SDK      │   │  API Client (apiClient.ts) │    │
│  │  @insforge/sdk     │   │  fetch → FastAPI           │    │
│  │  Auth, Storage     │   │                            │    │
│  └────────┬───────────┘   └──────────────┬─────────────┘    │
└───────────┼──────────────────────────────┼──────────────────┘
            │ HTTPS (JWT auth)             │ HTTPS (REST)
            ▼                             ▼
┌───────────────────────────┐  ┌──────────────────────────────┐
│  InsForge Backend         │  │  FastAPI (services/api)      │
│  https://asp6i95i...      │  │  Python 3.11, uvicorn        │
│                           │  │                              │
│  • PostgreSQL 15          │  │  Routes:                     │
│  • Auth (Google/GitHub)   │◄─┤  GET /health                 │
│  • Storage (S3-compat)    │  │  GET /health/db              │
│  • PostgREST REST API     │  │  GET /health/storage         │
│  • Edge Functions         │  │  GET /api/me (JWT-protected) │
└───────────────────────────┘  └──────────────────────────────┘

            ┌──────────────────────────────────┐
            │  video-worker (Phase 4)           │
            │  Python, FFmpeg, background jobs  │
            │  Reads recordings → extracts clips│
            │  Uploads to InsForge Storage      │
            └──────────────────────────────────┘
```

## Technology Decisions

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | React 18 + Vite + TypeScript | Fast HMR, strong typing, well-supported ecosystem |
| Backend API | FastAPI + Python 3.11 | Async-native, auto-generated OpenAPI docs, pydantic validation |
| Database | InsForge PostgreSQL 15 | Managed Postgres with PostgREST, RLS, auth built-in |
| Auth | InsForge Auth | JWT-based, same surface as DB/Storage, Google + GitHub OAuth ready |
| Storage | InsForge Storage (S3-compat) | Video files, highlights clips, thumbnails — co-located with DB |
| Frontend ↔ Backend | REST (fetch / httpx) | Simple, debuggable, no extra client layer needed in Phase 0 |
| Migrations | InsForge CLI (`db migrations`) | Native to InsForge, SQL-based, versioned |
| Video processing | FFmpeg (Phase 4) | Industry standard, runs in a background worker |

## Folder Structure

```
cricket-highlights/
├── apps/
│   └── web/                    ← React + Vite SPA
│       ├── src/
│       │   ├── components/     ← Shared UI components
│       │   ├── features/       ← Feature modules (Phase 1+)
│       │   ├── hooks/          ← React hooks (useAuth, etc.)
│       │   ├── services/       ← API client, InsForge client
│       │   ├── types/          ← TypeScript interfaces
│       │   └── theme/          ← Design tokens
│       └── tests/
├── services/
│   ├── api/                    ← FastAPI backend
│   │   ├── app/
│   │   │   ├── api/routes/     ← HTTP route handlers
│   │   │   ├── core/           ← Config, logging, auth, DB client
│   │   │   ├── models/         ← (Phase 1+) ORM/schema models
│   │   │   ├── schemas/        ← Pydantic schemas
│   │   │   └── services/       ← Business logic services
│   │   └── tests/
│   └── video-worker/           ← Phase 4 FFmpeg worker placeholder
├── migrations/                 ← InsForge SQL migrations (npx @insforge/cli)
└── docs/
```

## Security Model

- **Frontend** only holds the InsForge anon key (`VITE_INSFORGE_ANON_KEY`). Row-level security enforces what an anon user can access.
- **FastAPI** holds the InsForge API key (`INSFORGE_API_KEY`) — admin/service-role equivalent. Server-side only, never sent to the browser.
- **JWT flow**: User signs in via InsForge Auth (frontend), receives a JWT. JWT is passed to FastAPI as `Authorization: Bearer <token>`. FastAPI verifies it and returns user-scoped data.
- **CORS**: FastAPI only accepts origins listed in `CORS_ORIGINS` env var.

## Phase Roadmap

| Phase | What's added |
|-------|-------------|
| 0 ✅ | Foundation: auth plumbing, health checks, storage bucket, migrations baseline |
| 1 | Database: teams, squads, players, matches, playing XI tables + RLS |
| 2 | Scoring engine: ball-by-ball deliveries, innings, player stats |
| 3 | Mobile recording markers: timestamps linked to deliveries |
| 4 | Clip extraction: FFmpeg worker, automatic player-wise clips |
| 5 | Milestones: animated celebrations for 50, 100, 150, 200 |
| 6 | Production readiness: search, security audit, backup strategy |
