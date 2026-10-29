import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from app.schemas.api import MagicLinkResolutionResponse, UserLessonResponse
from app.services.lesson_service import lesson_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Lessons"])

@router.get(
    "/api/lesson/{token}",
    response_model=MagicLinkResolutionResponse,
    summary="Resolve Ephemeral Magic Link Token",
    description="Resolves magic link token from /lesson/{token}, verifying expiration, revocation, and user status before returning the bound lesson exercises."
)
async def get_lesson_by_token(token: str):
    res = lesson_service.resolve_magic_link(token)
    if res.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session Expired. This magic link has exceeded its validity window.",
        )
    if res.status in ("not_found", "revoked"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Magic link {res.status}.",
        )
    if res.status == "user_inactive":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )
    return res

@router.get(
    "/api/user/{email}/latest-lesson",
    response_model=UserLessonResponse,
    summary="Zero-Auth Query for latest lesson",
    description="Finds highest sequential lesson for an active, subscribed user."
)
async def get_user_latest_lesson(email: str, course: Optional[str] = None):
    return lesson_service.resolve_user_latest_lesson(email=email, course_name=course)
