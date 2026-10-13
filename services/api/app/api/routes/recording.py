"""
Recording and event markers routes — Phase 3 video-to-delivery synchronization.
"""
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user, require_user_id
from app.core.database import InsForgeClient, get_insforge_client
from app.schemas.recording import (
    EventMarkerCreate,
    EventMarkerLinkDelivery,
    EventMarkerResponse,
    EventMarkerUpdate,
    RecordingSessionCreate,
    RecordingSessionResponse,
    RecordingSessionUpdate,
    VideoSegmentCreate,
    VideoSegmentResponse,
)
from app.services import recording as recording_svc

router = APIRouter(tags=["recording"])
_bearer = HTTPBearer(auto_error=True)


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.post("/api/matches/{match_id}/recordings", response_model=RecordingSessionResponse, status_code=201)
async def create_recording_session(
    match_id: str,
    body: RecordingSessionCreate,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    owner_id = require_user_id(current_user)
    return await recording_svc.create_recording_session(
        db, match_id, owner_id, body, credentials.credentials
    )


@router.post("/api/recording-sessions", response_model=RecordingSessionResponse, status_code=201)
async def create_recording_session_contract(
    body: RecordingSessionCreate,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    if not body.match_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="match_id is required in request body")
    owner_id = require_user_id(current_user)
    return await recording_svc.create_recording_session(
        db, str(body.match_id), owner_id, body, credentials.credentials
    )


@router.get("/api/matches/{match_id}/recordings", response_model=List[RecordingSessionResponse])
async def list_recording_sessions(
    match_id: str,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    owner_id = require_user_id(current_user)
    return await recording_svc.list_recording_sessions(db, match_id, owner_id=owner_id)


@router.get("/api/recordings/{session_id}", response_model=RecordingSessionResponse)
async def get_recording_session(
    session_id: str,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    owner_id = require_user_id(current_user)
    return await recording_svc.get_recording_session(db, session_id, owner_id=owner_id)


@router.patch("/api/recordings/{session_id}", response_model=RecordingSessionResponse)
async def update_recording_session(
    session_id: str,
    body: RecordingSessionUpdate,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    owner_id = require_user_id(current_user)
    return await recording_svc.update_recording_session(
        db, session_id, body, credentials.credentials, owner_id=owner_id
    )


@router.delete("/api/recordings/{session_id}", status_code=204)
async def delete_recording_session(
    session_id: str,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> None:
    owner_id = require_user_id(current_user)
    await recording_svc.delete_recording_session(
        db, session_id, credentials.credentials, owner_id=owner_id
    )


# ── Video Segments ────────────────────────────────────────────────────────────

@router.post("/api/recordings/{session_id}/segments", response_model=VideoSegmentResponse, status_code=201)
async def add_segment(
    session_id: str,
    body: VideoSegmentCreate,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await recording_svc.add_segment(db, session_id, body, credentials.credentials)


@router.post("/api/recordings/{session_id}/upload", response_model=RecordingSessionResponse)
async def upload_session_video(
    session_id: str,
    file: Annotated[UploadFile, File(...)],
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    content = await file.read()
    return await recording_svc.upload_session_video(
        db=db,
        session_id=session_id,
        filename=file.filename or "recording.webm",
        content=content,
        content_type=file.content_type or "video/webm",
        token=credentials.credentials,
    )


# ── Event Markers ─────────────────────────────────────────────────────────────

@router.post("/api/recordings/{session_id}/markers", response_model=EventMarkerResponse, status_code=201)
@router.post("/api/recording-sessions/{session_id}/markers", response_model=EventMarkerResponse, status_code=201)
async def create_marker(
    session_id: str,
    body: EventMarkerCreate,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await recording_svc.create_marker(db, session_id, body, credentials.credentials)


@router.get("/api/recordings/{session_id}/markers", response_model=List[EventMarkerResponse])
@router.get("/api/recording-sessions/{session_id}/markers", response_model=List[EventMarkerResponse])
async def list_markers(
    session_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await recording_svc.list_markers(db, session_id)


@router.post("/api/markers/{marker_id}/link", response_model=EventMarkerResponse)
async def link_marker(
    marker_id: str,
    body: EventMarkerLinkDelivery,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await recording_svc.link_marker_to_delivery(
        db, marker_id, body, credentials.credentials
    )


@router.patch("/api/markers/{marker_id}", response_model=EventMarkerResponse)
async def update_marker(
    marker_id: str,
    body: EventMarkerUpdate,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await recording_svc.update_marker(db, marker_id, body, credentials.credentials)


@router.delete("/api/markers/{marker_id}", status_code=204)
async def delete_marker(
    marker_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> None:
    await recording_svc.delete_marker(db, marker_id, credentials.credentials)
