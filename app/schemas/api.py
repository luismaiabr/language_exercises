from datetime import date as dt_date, datetime
from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

from app.schemas.db import Exercise_db

# ==========================================
# API REQUEST & RESPONSE PAYLOADS
# ==========================================

class WebhookIngestionPayload(BaseModel):
    """Payload sent by n8n: only recipient and raw lesson text."""
    email: EmailStr
    course_name: str = "German Theory"
    date: dt_date = Field(default_factory=dt_date.today)
    raw_text: str = Field(..., min_length=1, description="Raw lesson (theory email) text.")
    instant_dispatch: Optional[bool] = Field(
        default=None,
        description="Override instant delivery on creation (True sends immediately and bypasses scheduler queue).",
    )

class IngestionResponse(BaseModel):
    """Status returned by webhook endpoint to n8n."""
    status: Literal["accepted", "processed", "skipped_inactive", "duplicate", "error"]
    message: str
    user_id: Optional[UUID] = None
    lesson: Optional[int] = None
    magic_link_url: Optional[str] = None
    magic_link_token: Optional[str] = None
    exercise_count: Optional[int] = None
    dispatched_instantly: Optional[bool] = None

class WrittenEvaluationRequest(BaseModel):
    """Payload sent by the frontend when submitting a written answer by exercise_id."""
    exercise_id: UUID = Field(..., description="ID of the Exercise_db row for context lookup.")
    question_prompt: str = Field(..., description="The specific WrittenExercise.question text.")
    user_answer: str = Field(..., min_length=1, description="The raw text typed by the user.")

class DynamicWrittenEvaluationRequest(BaseModel):
    """Protected written answer evaluation requiring the valid magic link token."""
    token: str = Field(..., description="The magic link token passed from the client session.")
    question_prompt: str = Field(..., description="Prompt of the written exercise.")
    user_answer: str = Field(..., min_length=1, description="The text written by the student.")
    exercise_id: Optional[UUID] = Field(default=None, description="Optional exercise ID if known.")

class WrittenEvaluationResponse(BaseModel):
    """Real-time AI evaluation returned to the frontend."""
    is_correct: bool = Field(
        ...,
        description="True if the user's German answer is grammatically and semantically valid."
    )
    explanation: str = Field(
        ...,
        description="If correct: explains why it works. If incorrect: explains the error and states the exact correct answer."
    )

class MagicLinkResolutionResponse(BaseModel):
    """Payload delivered to frontend when opening /lesson/{token}."""
    is_valid: bool
    status: Literal["active", "expired", "revoked", "not_found", "user_inactive"]
    expires_at: Optional[datetime] = None
    lesson: Optional[int] = None
    course_name: Optional[str] = None
    user_name: Optional[str] = None
    lesson_exercises: Optional[List[Exercise_db]] = Field(
        default=None,
        description="The exercises in the bound lesson if the token is valid."
    )

class UserLessonResponse(BaseModel):
    """Response when querying /<email>/ directly."""
    is_active: bool
    is_subscribed: bool
    status: Literal["active", "inactive", "unsubscribed", "no_lessons"]
    lesson: Optional[int] = None
    course_name: Optional[str] = None
    user_name: Optional[str] = None
    lesson_exercises: Optional[List[Exercise_db]] = None

class RecordAnswerRequest(BaseModel):
    """Record an answered question into the answers table."""
    exercise_id: UUID
    user_id: Optional[UUID] = None
    token: Optional[str] = None
    answer: str
    date: dt_date = Field(default_factory=dt_date.today)

class RecordAnswerResponse(BaseModel):
    success: bool
    answer_id: UUID
    message: str
