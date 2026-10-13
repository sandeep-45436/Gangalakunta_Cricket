"""Tests for health-check endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "cricket-api"


@pytest.mark.asyncio
async def test_root(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "cricket-api"
    assert "docs" in data


@pytest.mark.asyncio
async def test_health_db_graceful(client: AsyncClient) -> None:
    """GET /health/db returns a structured response (200 or 503)."""
    response = await client.get("/health/db")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "db" in data


@pytest.mark.asyncio
async def test_health_storage_graceful(client: AsyncClient) -> None:
    """GET /health/storage returns a structured response."""
    response = await client.get("/health/storage")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
