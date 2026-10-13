# API Reference — Cricket Highlights

Base URL (local dev): `http://localhost:8000`  
Auto-generated interactive docs: `http://localhost:8000/docs`

---

## Health Endpoints

### GET /health

Liveness check. No external calls.

**Response 200**
```json
{
  "status": "ok",
  "service": "cricket-api"
}
```

---

### GET /health/db

Checks InsForge PostgreSQL (PostgREST) connectivity.

**Response 200** — DB reachable
```json
{
  "status": "ok",
  "db": "connected",
  "provider": "insforge"
}
```

**Response 503** — DB unreachable
```json
{
  "status": "error",
  "db": "unreachable",
  "provider": "insforge"
}
```

---

### GET /health/storage

Checks InsForge Storage connectivity and whether the `cricket-videos` bucket exists.

**Response 200** — Storage reachable
```json
{
  "status": "ok",
  "storage": "reachable",
  "bucket": "cricket-videos",
  "bucket_exists": true
}
```

**Response 503** — Storage unreachable
```json
{
  "status": "error",
  "storage": "unreachable",
  "detail": "<reason>"
}
```

---

## Auth Endpoints

### GET /api/me

Returns the currently authenticated user's identity. Requires a valid InsForge JWT.

**Headers**
```
Authorization: Bearer <insforge_access_token>
```

**Response 200**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "role": "authenticated"
}
```

**Response 401** — Token expired or invalid
```json
{
  "detail": "Token has expired"
}
```

**Response 403** — No token provided
```json
{
  "detail": "Not authenticated"
}
```

---

## Scoring & Innings Endpoints (Phase 2)

All scoring endpoints require authentication (`Authorization: Bearer <token>`).

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/matches/{match_id}/innings` | Start innings with openers and bowler |
| `GET` | `/api/matches/{match_id}/innings` | List innings for match |
| `GET` | `/api/innings/{innings_id}` | Get innings details & live state |
| `PATCH` | `/api/innings/{innings_id}` | Update innings state (bowler, strike, status) |
| `GET` | `/api/innings/{innings_id}/scorecard` | Full deterministic innings scorecard |
| `GET` | `/api/matches/{match_id}/scorecard` | Full match scorecard across all innings with match result |
| `GET` | `/api/innings/{innings_id}/deliveries` | List ball-by-ball canonical deliveries |
| `POST` | `/api/innings/{innings_id}/deliveries` | Record canonical delivery (idempotent) |
| `POST` | `/api/deliveries/{delivery_id}/void` | Void delivery with audited reason and auto-resync |
| `PATCH` | `/api/deliveries/{delivery_id}` | Edit delivery with version bump and auto-resync |

