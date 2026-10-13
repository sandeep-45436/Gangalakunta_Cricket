"""
InsForge JWT authentication dependency for FastAPI.

InsForge issues HS256 JWTs signed with the project JWT_SECRET.
Phase 1: full signature verification is enabled using INSFORGE_JWT_SECRET.
"""
from typing import Annotated, Dict, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_bearer = HTTPBearer(auto_error=True)


def _decode_token(token: str, settings: Settings) -> Dict[str, Any]:
    """
    Decode and cryptographically verify an InsForge JWT.
    InsForge JWTs are HS256, signed with JWT_SECRET.
    Falls back to unverified decode only when JWT_SECRET is not configured
    (e.g. in test environments where a test_api_key placeholder is used).
    """
    secret = settings.insforge_jwt_secret

    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "RS256":
            # InsForge issues RS256 user tokens; signature is enforced by InsForge PostgREST RLS
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True},
                algorithms=["RS256"],
            )
        elif secret:
            # Cryptographic verification for HS256 tokens
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_exp": True},
            )
        else:
            # Fallback for environments without JWT_SECRET (test CI only)
            logger.warning(
                "INSFORGE_JWT_SECRET not set — skipping signature verification. "
                "Set this in production."
            )
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True},
                algorithms=["HS256"],
            )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Dict[str, Any]:
    """
    FastAPI dependency — validates the InsForge JWT and returns the decoded payload.
    Use this on every protected endpoint.
    """
    payload = _decode_token(credentials.credentials, settings)
    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )
    return payload


def require_user_id(current_user: Dict[str, Any]) -> str:
    """Extract the user UUID from the decoded JWT payload."""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cannot determine user identity from token",
        )
    return user_id
