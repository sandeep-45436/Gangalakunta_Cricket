"""
Pytest fixtures for the Cricket Highlights API.
Sets env vars before any app imports so pydantic-settings picks them up.
"""
import os
import sys

# Ensure services/api is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must be set BEFORE importing app so pydantic-settings reads them
os.environ.setdefault("INSFORGE_URL", "https://asp6i95i.ap-southeast.insforge.app")
os.environ.setdefault("INSFORGE_ANON_KEY", "test_anon_key")
os.environ.setdefault("INSFORGE_API_KEY", "test_api_key")
os.environ.setdefault("INSFORGE_JWT_SECRET", "")   # empty → signature verify skipped in tests
os.environ.setdefault("INSFORGE_DB_URL", "")
os.environ.setdefault("API_DEBUG", "false")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Async HTTP client wired to the FastAPI app (no real network)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
