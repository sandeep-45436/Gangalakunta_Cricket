"""
Scoring and delivery routes — Phase 2 ball-by-ball scoring engine.
"""
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.database import InsForgeClient, get_insforge_client
from app.schemas.scoring import (
    DeliveryCreate,
    DeliveryUpdate,
    DeliveryVoidRequest,
    InningsScorecard,
    InningsStartRequest,
    InningsUpdateRequest,
    MatchScorecard,
)
from app.services import scoring as scoring_svc

router = APIRouter(tags=["scoring"])
_bearer = HTTPBearer(auto_error=True)


# ── Innings endpoints ─────────────────────────────────────────────────────────

@router.post("/api/matches/{match_id}/innings", status_code=201)
async def start_innings(
    match_id: str,
    body: InningsStartRequest,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await scoring_svc.start_innings(db, match_id, body, credentials.credentials)


@router.get("/api/matches/{match_id}/innings")
async def list_match_innings(
    match_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await scoring_svc.list_innings_for_match(db, match_id)


@router.get("/api/innings/{innings_id}")
async def get_innings(
    innings_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await scoring_svc.get_innings(db, innings_id)


@router.patch("/api/innings/{innings_id}")
async def update_innings(
    innings_id: str,
    body: InningsUpdateRequest,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await scoring_svc.update_innings_state(db, innings_id, body, credentials.credentials)


@router.get("/api/innings/{innings_id}/scorecard", response_model=InningsScorecard)
async def get_innings_scorecard(
    innings_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await scoring_svc.get_scorecard(db, innings_id)


@router.get("/api/matches/{match_id}/scorecard", response_model=MatchScorecard)
async def get_match_scorecard(
    match_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await scoring_svc.get_match_scorecard(db, match_id)


# ── Delivery endpoints ───────────────────────────────────────────────────────

@router.get("/api/innings/{innings_id}/deliveries")
async def list_deliveries(
    innings_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await db.select(
        "deliveries",
        filters={"innings_id": f"eq.{innings_id}"},
        order="sequence_no.asc",
        limit=500,
    )


@router.post("/api/innings/{innings_id}/deliveries", status_code=201)
async def record_delivery(
    innings_id: str,
    body: DeliveryCreate,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await scoring_svc.record_delivery(db, innings_id, body, credentials.credentials)


@router.post("/api/deliveries/{delivery_id}/void")
async def void_delivery(
    delivery_id: str,
    body: DeliveryVoidRequest,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await scoring_svc.void_delivery(db, delivery_id, body, credentials.credentials)


@router.patch("/api/deliveries/{delivery_id}")
async def update_delivery(
    delivery_id: str,
    body: DeliveryUpdate,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await scoring_svc.update_delivery(db, delivery_id, body, credentials.credentials)
