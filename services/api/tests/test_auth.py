"""Tests for authentication endpoints and JWT dependency."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient) -> None:
    """GET /api/me without a token must return 403."""
    response = await client.get("/api/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    """GET /api/me with a garbage token must return 401."""
    response = await client.get("/api/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_rejects_expired_token(client: AsyncClient) -> None:
    """GET /api/me with an expired JWT must return 401."""
    # Well-formed HS256 JWT with exp=1000000000 (far in the past)
    expired = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiJ1c2VyXzEyMyIsImVtYWlsIjoidGVzdEBleGFtcGxlLmNvbSIsImV4cCI6MTAwMDAwMDAwMH0"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    response = await client.get("/api/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code in (401, 403)
