"""
API routes for Phase 6 — Player Profiles, Historical Match Archive,
Signed Media Access, Retry/Recovery Workflows, Retention & Backup Verification.
"""
from typing import Annotated, Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user, require_user_id
from app.core.database import InsForgeClient, get_insforge_client
from app.schemas.archive import (
    BackupManifestResponse,
    BackupVerifyRequest,
    BackupVerifyResponse,
    MatchArchivePageResponse,
    OpsDiagnosticsResponse,
    PlayerProfileResponse,
    RetentionCleanupRequest,
    RetentionCleanupResponse,
    RetryJobsResult,
    SignedMediaUrlResponse,
)
from app.services import archive as archive_svc

router = APIRouter(tags=["archive & ops"])
_bearer = HTTPBearer(auto_error=True)


@router.get(
    "/api/players/{player_id}/profile",
    response_model=PlayerProfileResponse,
    summary="Get complete player profile with team history, career & match stats, milestones, and paginated highlights",
)
async def get_player_profile(
    player_id: UUID,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    match_id: Optional[UUID] = Query(default=None),
    tournament: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=12, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    owner_id = require_user_id(current_user)
    return await archive_svc.get_player_profile(
        db=db,
        player_id=str(player_id),
        owner_id=owner_id,
        match_id=str(match_id) if match_id else None,
        tournament=tournament,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/archive/matches",
    response_model=MatchArchivePageResponse,
    summary="Search and filter historical matches with pagination",
)
async def search_match_archive(
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    q: Optional[str] = Query(default=None),
    team_id: Optional[UUID] = Query(default=None),
    team_b_id: Optional[UUID] = Query(default=None),
    player_id: Optional[UUID] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    format: Optional[str] = Query(default=None),
    tournament: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    innings_number: Optional[int] = Query(default=None, ge=1, le=4),
    highlight_type: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    owner_id = require_user_id(current_user)
    return await archive_svc.search_match_archive(
        db=db,
        owner_id=owner_id,
        q=q,
        team_id=str(team_id) if team_id else None,
        team_b_id=str(team_b_id) if team_b_id else None,
        player_id=str(player_id) if player_id else None,
        date_from=date_from,
        date_to=date_to,
        format_filter=format,
        tournament=tournament,
        status_filter=status,
        innings_number=innings_number,
        highlight_type=highlight_type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/api/media/sign",
    response_model=SignedMediaUrlResponse,
    summary="Generate an expiring HMAC-signed URL for private media after verifying ownership",
)
async def sign_media_url(
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    key: str = Query(..., min_length=1),
):
    owner_id = require_user_id(current_user)
    return await archive_svc.generate_signed_media_url(
        db=db,
        key=key,
        owner_id=owner_id,
    )


@router.get(
    "/api/ops/diagnostics",
    response_model=OpsDiagnosticsResponse,
    summary="Production observability, job health metrics, and recent audit log feed",
)
async def get_ops_diagnostics(
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    owner_id = require_user_id(current_user)
    return await archive_svc.get_ops_diagnostics(db=db, owner_id=owner_id)


@router.post(
    "/api/ops/jobs/retry-failed",
    response_model=RetryJobsResult,
    summary="Retry failed/stuck highlight jobs and recover interrupted recording sessions",
)
async def retry_failed_jobs(
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    match_id: Optional[UUID] = Query(default=None),
):
    owner_id = require_user_id(current_user)
    return await archive_svc.retry_failed_jobs_and_sessions(
        db=db,
        owner_id=owner_id,
        token=credentials.credentials,
        match_id=str(match_id) if match_id else None,
    )


@router.post(
    "/api/ops/retention/apply",
    response_model=RetentionCleanupResponse,
    summary="Apply media retention policy to purge expired raw recordings while preserving highlight clips",
)
async def apply_retention_policy(
    body: RetentionCleanupRequest,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    owner_id = require_user_id(current_user)
    return await archive_svc.apply_retention_policy(
        db=db,
        owner_id=owner_id,
        token=credentials.credentials,
        retention_days=body.retention_days,
        dry_run=body.dry_run,
    )


@router.get(
    "/api/ops/backup/export",
    response_model=BackupManifestResponse,
    summary="Export a checksummed JSON backup archive of all user matches, scorecards, milestones, and highlights",
)
async def export_backup(
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    owner_id = require_user_id(current_user)
    return await archive_svc.export_owner_backup(
        db=db, owner_id=owner_id, token=credentials.credentials
    )


@router.post(
    "/api/ops/backup/verify",
    response_model=BackupVerifyResponse,
    summary="Verify cryptographic SHA-256 checksum and structural completeness of a backup archive",
)
async def verify_backup(
    body: BackupVerifyRequest,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
):
    require_user_id(current_user)
    return archive_svc.verify_backup_manifest(
        expected_checksum=body.checksum_sha256,
        data=body.data,
    )
