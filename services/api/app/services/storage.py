"""
InsForge Storage service wrapper.

Server-side only. Uses the admin API key — never expose this to the frontend.
"""
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CRICKET_VIDEOS_BUCKET = "cricket-videos"


class StorageService:
    """Thin wrapper around InsForge Storage REST API."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = f"{settings.insforge_url}/storage/v1"
        self._headers = {
            "apikey": settings.insforge_api_key,
            "Authorization": f"Bearer {settings.insforge_api_key}",
        }

    async def ensure_bucket(self, bucket_name: str = CRICKET_VIDEOS_BUCKET) -> Dict[str, Any]:
        """Create the bucket if it does not already exist."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Check if exists first
            resp = await client.get(
                f"{self._base_url}/bucket/{bucket_name}",
                headers=self._headers,
            )
            if resp.status_code == 200:
                logger.info("Bucket '%s' already exists", bucket_name)
                return resp.json()

            # Create it
            resp = await client.post(
                f"{self._base_url}/bucket",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"id": bucket_name, "name": bucket_name, "public": False},
            )
            resp.raise_for_status()
            logger.info("Bucket '%s' created", bucket_name)
            return resp.json()

    async def list_objects(
        self,
        bucket_name: str = CRICKET_VIDEOS_BUCKET,
        prefix: str = "",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """List objects in a bucket."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._base_url}/object/list/{bucket_name}",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"prefix": prefix, "limit": limit, "offset": 0},
            )
            resp.raise_for_status()
            return resp.json()
