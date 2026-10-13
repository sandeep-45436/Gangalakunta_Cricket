"""
Tests for route-level authorization — all Phase 1–6 endpoints and
Cross-Phase Specification (2.1) contract routes must require authentication,
and unauthenticated requests must be rejected.
"""
import pytest
from httpx import AsyncClient


PROTECTED_ROUTES = [
    ("GET",    "/api/teams"),
    ("POST",   "/api/teams"),
    ("GET",    "/api/teams/some-uuid"),
    ("PATCH",  "/api/teams/some-uuid"),
    ("DELETE", "/api/teams/some-uuid"),
    ("GET",    "/api/teams/some-uuid/squad"),
    ("POST",   "/api/teams/some-uuid/squad"),
    ("GET",    "/api/players"),
    ("POST",   "/api/players"),
    ("GET",    "/api/players/some-uuid"),
    ("PATCH",  "/api/players/some-uuid"),
    ("DELETE", "/api/players/some-uuid"),
    ("GET",    "/api/matches"),
    ("POST",   "/api/matches"),
    ("GET",    "/api/matches/some-uuid"),
    ("PATCH",  "/api/matches/some-uuid"),
    ("PUT",    "/api/matches/some-uuid/playing-xi"),
    ("GET",    "/api/matches/some-uuid/playing-xi/team-uuid"),
    ("POST",   "/api/matches/some-uuid/substitutes"),
    ("GET",    "/api/matches/some-uuid/substitutes"),
    ("POST",   "/api/matches/some-uuid/innings"),
    ("GET",    "/api/matches/some-uuid/innings"),
    ("GET",    "/api/innings/some-uuid"),
    ("PATCH",  "/api/innings/some-uuid"),
    ("GET",    "/api/innings/some-uuid/scorecard"),
    ("GET",    "/api/matches/some-uuid/scorecard"),
    ("GET",    "/api/innings/some-uuid/deliveries"),
    ("POST",   "/api/innings/some-uuid/deliveries"),
    ("POST",   "/api/deliveries/some-uuid/void"),
    ("PATCH",  "/api/deliveries/some-uuid"),
    ("POST",   "/api/matches/some-uuid/recordings"),
    ("POST",   "/api/recording-sessions"),
    ("GET",    "/api/matches/some-uuid/recordings"),
    ("GET",    "/api/recordings/some-uuid"),
    ("PATCH",  "/api/recordings/some-uuid"),
    ("DELETE", "/api/recordings/some-uuid"),
    ("POST",   "/api/recordings/some-uuid/segments"),
    ("POST",   "/api/recordings/some-uuid/markers"),
    ("POST",   "/api/recording-sessions/some-uuid/markers"),
    ("GET",    "/api/recordings/some-uuid/markers"),
    ("GET",    "/api/recording-sessions/some-uuid/markers"),
    ("POST",   "/api/markers/some-uuid/link"),
    ("PATCH",  "/api/markers/some-uuid"),
    ("DELETE", "/api/markers/some-uuid"),
    ("POST",   "/api/highlights/trigger"),
    ("POST",   "/api/highlights/process"),
    ("POST",   "/api/highlights/some-uuid/reprocess"),
    ("GET",    "/api/highlights/jobs/some-uuid"),
    ("GET",    "/api/players/some-uuid/highlights"),
    ("GET",    "/api/matches/some-uuid/highlights"),
    ("GET",    "/api/matches/some-uuid/milestones"),
    ("GET",    "/api/innings/some-uuid/milestones"),
    ("POST",   "/api/innings/some-uuid/milestones/recalculate"),
    ("GET",    "/api/players/some-uuid/milestones"),
    ("GET",    "/api/milestones/some-uuid"),
    # Phase 6 Archive & Production Ops routes
    ("GET",    "/api/players/some-uuid/profile"),
    ("GET",    "/api/archive/matches"),
    ("GET",    "/api/media/sign"),
    ("POST",   "/api/ops/jobs/retry-failed"),
    ("POST",   "/api/ops/retention/apply"),
    ("GET",    "/api/ops/diagnostics"),
    ("GET",    "/api/ops/backup/export"),
    ("POST",   "/api/ops/backup/verify"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
async def test_unauthenticated_request_rejected(
    client: AsyncClient,
    method: str,
    path: str,
) -> None:
    """Every protected endpoint must return 401 or 403 without a token."""
    response = await client.request(method, path, json={})
    assert response.status_code in (401, 403), (
        f"{method} {path} returned {response.status_code} — expected 401 or 403"
    )
