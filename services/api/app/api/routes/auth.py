"""
Auth routes — Phase 0 baseline.

GET /api/me — returns the current authenticated user's JWT claims.
             Protected: requires a valid InsForge JWT in Authorization header.
"""
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me", summary="Get current authenticated user")
async def get_me(
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
) -> Dict[str, Any]:
    """
    Returns the decoded JWT payload for the currently authenticated user.
    Use this endpoint to verify auth is wired correctly end-to-end.
    """
    return {
        "user_id": current_user.get("sub"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
    }
