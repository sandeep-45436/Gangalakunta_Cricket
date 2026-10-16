"""
API routes for AI Continuous Live Capture, Delivery Detection & LangGraph agents.
"""
from typing import Annotated, Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.database import InsForgeClient, get_insforge_client
from app.schemas.ai_capture import AICaptureResponse, AICaptureStreamRequest
from app.services import ai_capture as ai_capture_svc

router = APIRouter(prefix="/api/ai", tags=["ai-capture"])
_bearer = HTTPBearer(auto_error=True)


@router.post(
    "/analyze-stream",
    response_model=AICaptureResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze live continuous stream segment with LangGraph & Gemini Vision",
)
@router.post(
    "/auto-capture-delivery",
    response_model=AICaptureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Auto-capture delivery window, create marker, trigger highlight, and attribute to players",
)
async def auto_capture_delivery(
    req: AICaptureStreamRequest,
    background_tasks: BackgroundTasks,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    """
    Executes the 4-agent LangGraph workflow:
    1. DeliverySegmenterAgent (run-up, delivery stride, release, impact)
    2. CricketEventRecognizerAgent (Gemini Multimodal Vision)
    3. ScoreCaptureFusionAgent (reconciles with live scorer input & clip offsets)
    4. PlayerReelPublisherAgent (ensures records & highlights MUST go to players)
    """
    return await ai_capture_svc.run_ai_capture_pipeline(
        db=db,
        req=req,
        token=credentials.credentials,
        background_tasks=background_tasks,
    )
