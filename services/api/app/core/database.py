"""
InsForge database client — server-side only, uses admin API key.

InsForge exposes PostgreSQL via PostgREST (REST API).
The FastAPI backend talks to InsForge through HTTP — never a raw Postgres connection.
"""
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class InsForgeClient:
    """
    Server-side client for InsForge REST (PostgREST + Auth + Storage) API.
    Uses the admin API key — never expose to frontend.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.insforge_url.rstrip("/")
        self._api_key = settings.insforge_api_key or settings.insforge_anon_key
        self._rest = f"{self._base_url}/api/database/records"
        self._headers = self.default_headers

    @property
    def default_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if self._api_key and self._api_key.strip():
            headers["apikey"] = self._api_key.strip()
            headers["Authorization"] = f"Bearer {self._api_key.strip()}"
        return headers

    @property
    def storage_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self._api_key and self._api_key.strip():
            headers["apikey"] = self._api_key.strip()
            headers["Authorization"] = f"Bearer {self._api_key.strip()}"
        return headers

    # ── connectivity ──────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.get(f"{self._rest}/matches", headers=self._headers, params={"limit": 1})
                return resp.status_code in (200, 206)
        except Exception as exc:
            logger.error("InsForge DB ping failed: %s", exc)
            return False

    # ── generic CRUD ──────────────────────────────────────────────────────────

    async def select(
        self,
        table: str,
        select: str = "*",
        filters: Optional[Dict[str, str]] = None,
        limit: int = 200,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """SELECT rows from a table. filters use PostgREST operator syntax."""
        params: Dict[str, Any] = {"select": select, "limit": limit}
        if filters:
            params.update(filters)
        if order:
            params["order"] = order
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.get(
                f"{self._rest}/{table}",
                headers=self._headers,
                params=params,
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[return-value]

    async def select_one(
        self,
        table: str,
        filters: Dict[str, str],
        select: str = "*",
    ) -> Optional[Dict[str, Any]]:
        """Return the first matching row, or None."""
        rows = await self.select(table, select=select, filters=filters, limit=1)
        return rows[0] if rows else None

    async def insert(
        self,
        table: str,
        rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """INSERT rows (must be a list per InsForge pattern). Returns inserted rows."""
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.post(
                f"{self._rest}/{table}",
                headers=self._headers,
                json=rows,
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else [data]

    async def update(
        self,
        table: str,
        filters: Dict[str, str],
        values: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """UPDATE rows matching filters. Returns updated rows."""
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.patch(
                f"{self._rest}/{table}",
                headers=self._headers,
                params=filters,
                json=values,
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else [data]

    async def delete(
        self,
        table: str,
        filters: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """DELETE rows matching filters. Returns deleted rows."""
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.delete(
                f"{self._rest}/{table}",
                headers=self._headers,
                params=filters,
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else ([data] if data else [])

    # ── convenience for user-scoped calls (passes user JWT, honours RLS) ──────

    def user_headers(self, token: str) -> Dict[str, str]:
        """
        Return headers that impersonate the signed-in user.
        PostgREST evaluates RLS policies using auth.uid() from this token.
        Use for INSERT/UPDATE/DELETE to enforce ownership policies.
        """
        headers = {
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if self._api_key and self._api_key.strip():
            headers["apikey"] = self._api_key.strip()
        auth_token = (token or "").strip()
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        elif self._api_key and self._api_key.strip():
            headers["Authorization"] = f"Bearer {self._api_key.strip()}"
        return headers

    async def insert_as_user(
        self,
        table: str,
        rows: List[Dict[str, Any]],
        token: str,
    ) -> List[Dict[str, Any]]:
        """INSERT rows using the user's JWT so RLS WITH CHECK fires."""
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.post(
                f"{self._rest}/{table}",
                headers=self.user_headers(token),
                json=rows,
            )
            if resp.status_code == 403:
                from fastapi import HTTPException, status as http_status
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="Permission denied by database policy",
                )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else [data]

    async def update_as_user(
        self,
        table: str,
        filters: Dict[str, str],
        values: Dict[str, Any],
        token: str,
    ) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.patch(
                f"{self._rest}/{table}",
                headers=self.user_headers(token),
                params=filters,
                json=values,
            )
            if resp.status_code == 403:
                from fastapi import HTTPException, status as http_status
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="Permission denied by database policy",
                )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else [data]

    async def delete_as_user(
        self,
        table: str,
        filters: Dict[str, str],
        token: str,
    ) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15.0) as c:
            resp = await c.delete(
                f"{self._rest}/{table}",
                headers=self.user_headers(token),
                params=filters,
            )
            if resp.status_code == 403:
                from fastapi import HTTPException, status as http_status
                raise HTTPException(
                    status_code=http_status.HTTP_403_FORBIDDEN,
                    detail="Permission denied by database policy",
                )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else ([data] if data else [])

    # ── storage ───────────────────────────────────────────────────────────────

    async def storage_ping(self, bucket: str) -> bool:
        url = f"{self._base_url}/api/storage/buckets/{bucket}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.get(url, headers=self.storage_headers)
                return resp.status_code in (200, 404)
        except Exception as exc:
            logger.error("Storage ping failed: %s", exc)
            return False

    async def upload_storage_file(
        self,
        bucket: str,
        filename: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        """Upload a file to InsForge storage. Returns {'key': ..., 'url': ..., 'size': ...}."""
        url = f"{self._base_url}/api/storage/buckets/{bucket}/objects"
        files = {"file": (filename, content, content_type)}
        async with httpx.AsyncClient(timeout=60.0) as c:
            resp = await c.post(url, headers=self.storage_headers, files=files)
            resp.raise_for_status()
            return resp.json()

    async def download_storage_file(self, bucket: str, key: str) -> bytes:
        """Download raw bytes from InsForge storage by key."""
        url = f"{self._base_url}/api/storage/buckets/{bucket}/objects/{key}"
        async with httpx.AsyncClient(timeout=60.0) as c:
            resp = await c.get(url, headers=self.storage_headers)
            resp.raise_for_status()
            return resp.content

    async def delete_storage_file(self, bucket: str, key: str) -> bool:
        """Delete an object from InsForge storage by key."""
        url = f"{self._base_url}/api/storage/buckets/{bucket}/objects/{key}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as c:
                resp = await c.delete(url, headers=self.storage_headers)
                return resp.status_code in (200, 204)
        except Exception as exc:
            logger.error("Storage delete failed: %s", exc)
            return False


def get_insforge_client() -> InsForgeClient:
    """FastAPI dependency — returns an InsForge client instance."""
    return InsForgeClient()

