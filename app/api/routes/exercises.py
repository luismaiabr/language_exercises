import logging
from typing import Optional, Union
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.db.supabase_client import supabase_service
from app.schemas.api import DynamicWrittenEvaluationRequest, WrittenEvaluationRequest, WrittenEvaluationResponse
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/exercises", tags=["Exercise Evaluation"])

class UnifiedWrittenEvaluationRequest(BaseModel):
    """Handles both token-based magic link session and direct exercise_id requests."""
    token: Optional[str] = Field(default=None, description="Magic link capability token.")
    exercise_id: Optional[UUID] = Field(default=None, description="Exercise UUID in database.")
    question_prompt: str = Field(..., min_length=1, description="Prompt given to the student.")
    user_answer: str = Field(..., min_length=1, description="Written answer submitted by the student.")

@router.post(
    "/evaluate-written",
    response_model=WrittenEvaluationResponse,
    summary="Dynamic Runtime AI Evaluation for Written Exercises",
    description="Evaluates a student's German written answer in real time using OpenRouter Gemini Flash, taking into account the lesson's grammar context."
)
async def evaluate_written_exercise(req: UnifiedWrittenEvaluationRequest):
    theory_summary: Optional[str] = None
    user_id: Optional[UUID] = None
    lesson_num: int = 1

    # 1. Check Magic Link token if provided
    if req.token:
        magic_link = supabase_service.get_magic_link_by_token(req.token)
        if magic_link:
            if not magic_link.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Cannot evaluate answer: session or token has expired or is revoked.",
                )
            user_id = magic_link.user_id
            lesson_num = magic_link.lesson

    # 2. Look up exercise context if exercise_id provided
    if req.exercise_id:
        exercise = supabase_service.get_exercise_by_id(req.exercise_id)
        if exercise:
            theory_summary = exercise.theory_summary
            user_id = user_id or exercise.user_id
            lesson_num = exercise.lesson

    # 3. Call AI service to evaluate written response
    eval_result = await ai_service.evaluate_written_answer(
        question_prompt=req.question_prompt,
        theory_summary=theory_summary,
        user_answer=req.user_answer,
    )

    # 4. Record answer in DB if exercise_id and user_id are known
    if req.exercise_id and user_id:
        try:
            supabase_service.record_answer(
                exercise_id=req.exercise_id,
                user_id=user_id,
                lesson=lesson_num,
                exercise_type="written",
                answer=req.user_answer,
            )
        except Exception as e:
            logger.warning(f"Failed to record written answer to database: {e}")

    return eval_result
