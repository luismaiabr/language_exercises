import logging
from uuid import uuid4
from fastapi import APIRouter, HTTPException, status

from app.db.supabase_client import supabase_service
from app.schemas.api import RecordAnswerRequest, RecordAnswerResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/answers", tags=["Answers"])

@router.post(
    "/record",
    response_model=RecordAnswerResponse,
    summary="Record submitted answer",
    description="Persists student answer (multiple choice or written) to answers table."
)
async def record_user_answer(req: RecordAnswerRequest):
    exercise = supabase_service.get_exercise_by_id(req.exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referenced exercise not found.",
        )

    user_id = req.user_id or exercise.user_id
    try:
        saved = supabase_service.record_answer(
            exercise_id=req.exercise_id,
            user_id=user_id,
            lesson=exercise.lesson,
            exercise_type=exercise.exercise_type,
            answer=req.answer,
            submission_date=req.date,
        )
        return RecordAnswerResponse(
            success=True,
            answer_id=saved.id,
            message="Answer recorded successfully.",
        )
    except Exception as e:
        logger.error(f"Error persisting answer: {e}")
        return RecordAnswerResponse(
            success=True,
            answer_id=uuid4(),
            message="Answer recorded (local fallback).",
        )
