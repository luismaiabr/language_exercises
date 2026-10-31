from datetime import date as dt_date, datetime, timezone
import secrets
from typing import List, Literal, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.exercise import ChoiceOption

# ==========================================
# SUPABASE DATABASE MODELS (*_db)
# ==========================================

class User_db(BaseModel):
    """Represents a row in the Supabase 'users' table."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Primary Key (UUID).")
    email: EmailStr = Field(..., description="Critical unique identifier used in /<email>/ routing.")
    name: str = Field(..., min_length=1, description="Full name or alias of the student.")
    is_active: bool = Field(default=True, description="Global kill-switch for user access.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Subscription_db(BaseModel):
    """Represents a row in the Supabase 'subscriptions' table."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Primary Key (UUID).")
    user_id: UUID = Field(..., description="Foreign Key referencing users.id.")
    course_name: str = Field(..., description="Identifier of the email course, e.g., 'German Theory'.")
    is_subscribed: bool = Field(default=True, description="Whether the user actively receives/accesses lessons.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Exercise_db(BaseModel):
    """Represents one row in the Supabase 'exercises' table."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Primary Key (UUID).")
    user_id: UUID = Field(..., description="Foreign Key referencing users.id.")
    subscription_id: Optional[UUID] = Field(default=None, description="Foreign Key referencing subscriptions.id.")
    date: dt_date = Field(default_factory=dt_date.today, description="The calendar date of the class.")
    lesson: int = Field(..., gt=0, description="Stable sequential lesson number.")
    exercise_type: Literal["multiple_choice", "written"]
    question: str = Field(..., min_length=1)
    options: Optional[List[ChoiceOption]] = Field(default=None, description="Choices for multiple-choice exercises.")
    theory_summary: Optional[str] = Field(
        default=None,
        description="Condensed context of the email theory; injected into the AI prompt when evaluating written answers."
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Answer_db(BaseModel):
    """Represents one row in the Supabase 'answers' table."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Primary Key (UUID).")
    exercise_id: UUID = Field(..., description="Foreign Key referencing exercises.id.")
    user_id: UUID = Field(..., description="Foreign Key referencing users.id.")
    date: dt_date = Field(default_factory=dt_date.today, description="Date the answer was submitted.")
    lesson: int = Field(..., gt=0, description="Lesson number copied from the exercise.")
    exercise_type: Literal["multiple_choice", "written"]
    answer: str = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MagicLink_db(BaseModel):
    """Represents a row in the Supabase 'magic_links' table."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="High-entropy URL-safe token used in /lesson/{token}."
    )
    user_id: UUID = Field(..., description="Foreign key to users.id.")
    subscription_id: UUID = Field(..., description="Foreign key to the user's subscription.")
    lesson: int = Field(..., gt=0, description="Lesson number bound to this token.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(..., description="Expiration timestamp calculated using MAGIC_LINK_TIMESPAN.")
    is_revoked: bool = Field(default=False, description="Manual revocation flag.")
    last_accessed_at: Optional[datetime] = Field(default=None)

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        target = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return now > target

    @property
    def is_valid(self) -> bool:
        return (not self.is_revoked) and (not self.is_expired)

class UserSchedule_db(BaseModel):
    """Represents a row in the Supabase 'user_schedules' table."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID = Field(..., description="Foreign key referencing users.id.")
    email: EmailStr = Field(..., description="User email for delivery.")
    course_name: str = Field(default="German Theory", description="Course / subject identifier.")
    lesson_id: int = Field(..., gt=0, description="Sequential lesson identifier / number.")
    when_to_send: datetime = Field(..., description="Target dispatch timestamp for the email.")
    status: Literal["pending", "sent", "failed", "cancelled"] = Field(
        default="pending", description="Dispatch delivery status."
    )
    sent_at: Optional[datetime] = Field(default=None, description="Timestamp when email was sent via SMTP.")
    error_message: Optional[str] = Field(default=None, description="Error details if delivery failed.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
