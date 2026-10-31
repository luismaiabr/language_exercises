import logging
from datetime import date as dt_date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from app.core.config import settings
from app.db.supabase_client import supabase_service
from app.schemas.api import (
    IngestionResponse,
    MagicLinkResolutionResponse,
    UserLessonResponse,
    WebhookIngestionPayload,
)
from app.schemas.db import Exercise_db, Subscription_db, User_db
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)

class LessonService:
    def __init__(self):
        self.db = supabase_service
        self.ai = ai_service

    async def ingest_webhook_lesson(self, payload: WebhookIngestionPayload) -> IngestionResponse:
        """
        Processes raw lesson text received from n8n.
        Enforces auto-provisioning, active-only generation, idempotency,
        sequential lesson numbering, AI generation, and magic link issuance.
        """
        email = payload.email.strip().lower()
        course_name = payload.course_name.strip()
        raw_text = payload.raw_text.strip()
        lesson_date = payload.date or dt_date.today()

        logger.info(f"Ingesting webhook for user {email}, course: '{course_name}'")

        # 1. Lookup User
        user = self.db.get_user_by_email(email)

        # 2. Auto-Provisioning (Inactive by Default)
        if not user:
            logger.info(f"User {email} not found. Auto-provisioning user as inactive (is_active=False).")
            # Create student user with is_active=False
            name_part = email.split("@")[0].replace(".", " ").title()
            user = self.db.create_user(email=email, name=name_part, is_active=False)
            
            # Create matching subscription record
            self.db.create_subscription(user_id=user.id, course_name=course_name, is_subscribed=True)

            return IngestionResponse(
                status="skipped_inactive",
                message="User was newly auto-provisioned as inactive. Lesson generation skipped until user is activated.",
                user_id=user.id,
            )

        # 3. Active-Only Generation Check
        if not user.is_active:
            logger.info(f"User {email} is inactive. Skipping lesson generation.")
            return IngestionResponse(
                status="skipped_inactive",
                message="User is inactive. Lesson generation skipped.",
                user_id=user.id,
            )

        # Check if this course/subject is newly created in the system.
        # If so, automatically subscribe all users to this new subject.
        if self.db.is_new_course(course_name):
            logger.info(f"New subject '{course_name}' detected. Auto-subscribing all users to this subject.")
            self.db.subscribe_all_users_to_course(course_name)

        # Check Subscription
        subscription = self.db.get_subscription(user.id, course_name)
        if not subscription:
            subscription = self.db.create_subscription(user_id=user.id, course_name=course_name, is_subscribed=True)
        elif not subscription.is_subscribed:
            logger.info(f"User {email} is unsubscribed from '{course_name}'. Skipping lesson generation.")
            return IngestionResponse(
                status="skipped_inactive",
                message=f"User is unsubscribed from course '{course_name}'. Lesson generation skipped.",
                user_id=user.id,
            )

        # 4. Idempotency Check
        text_hash = self.db.calculate_text_hash(email, course_name, raw_text)
        existing_lesson = self.db.check_existing_ingestion(user.id, course_name, text_hash)
        if existing_lesson:
            logger.info(f"Duplicate lesson text detected for user {email} (lesson {existing_lesson}). Skipping generation.")
            return IngestionResponse(
                status="duplicate",
                message="Duplicate raw text already ingested for this user and course.",
                user_id=user.id,
                lesson=existing_lesson,
            )

        # 5. Sequential Lesson Number Assignment
        highest_lesson = self.db.get_highest_lesson_number(user.id, subscription.id)
        next_lesson = highest_lesson + 1
        logger.info(f"Assigning sequential lesson number {next_lesson} to user {email}.")

        # 6. AI Lesson Generation via OpenRouter Gemini Flash
        generated = await self.ai.generate_lesson(
            course_name=course_name,
            date=lesson_date,
            raw_text=raw_text,
        )

        # 7. Persist Exercises in Supabase
        exercises_to_save = []
        for ex in generated.exercises:
            row_dict = {
                "user_id": user.id,
                "subscription_id": subscription.id,
                "date": lesson_date,
                "lesson": next_lesson,
                "exercise_type": ex.exercise_type,
                "question": ex.question,
                "options": [opt.model_dump() for opt in ex.options] if ex.exercise_type == "multiple_choice" else None,
                "theory_summary": generated.theory_summary,
            }
            exercises_to_save.append(row_dict)

        saved_exercises = self.db.save_exercises(exercises_to_save)

        # 8. Create Ephemeral Magic Link Capability Token
        magic_link = self.db.create_magic_link(
            user_id=user.id,
            subscription_id=subscription.id,
            lesson=next_lesson,
        )
        magic_link_url = f"{settings.magic_link_base_url}/{magic_link.token}"

        # 9. Record Ingestion Ledger for Idempotency
        self.db.record_ingestion(
            user_id=user.id,
            course_name=course_name,
            text_hash=text_hash,
            lesson=next_lesson,
        )

        # 10. Automatically schedule lessons for all users subscribed to this subject (1-day intervals)
        subscribers = self.db.get_subscribers_for_course(course_name, only_active_users=True)
        if user.is_active and not any(s.id == user.id for s in subscribers):
            subscribers.append(user)

        for sub_user in subscribers:
            # Replicate exercises and magic link for other subscribers so their link is ready
            if sub_user.id != user.id:
                sub_subscription = self.db.get_subscription(sub_user.id, course_name)
                sub_sid = sub_subscription.id if sub_subscription else None
                existing_sub_ex = self.db.get_exercises_by_lesson(sub_user.id, next_lesson, sub_sid)
                if not existing_sub_ex:
                    replicated_exercises = []
                    for ex in generated.exercises:
                        replicated_exercises.append({
                            "user_id": sub_user.id,
                            "subscription_id": sub_sid,
                            "date": lesson_date,
                            "lesson": next_lesson,
                            "exercise_type": ex.exercise_type,
                            "question": ex.question,
                            "options": [opt.model_dump() for opt in ex.options] if ex.exercise_type == "multiple_choice" else None,
                            "theory_summary": generated.theory_summary,
                        })
                    self.db.save_exercises(replicated_exercises)
                    if sub_sid:
                        self.db.create_magic_link(
                            user_id=sub_user.id,
                            subscription_id=sub_sid,
                            lesson=next_lesson,
                        )

            # Check if this lesson is already scheduled for this user
            existing_schedule = self.db.get_user_schedule(sub_user.id, course_name, next_lesson)
            if not existing_schedule:
                # Calculate when_to_send with 1-day interval
                latest_schedule = self.db.get_latest_schedule_for_user(sub_user.id, course_name)
                now_utc = datetime.now(timezone.utc)
                if latest_schedule:
                    latest_time = latest_schedule.when_to_send
                    if latest_time.tzinfo is None:
                        latest_time = latest_time.replace(tzinfo=timezone.utc)
                    when_to_send = latest_time + timedelta(days=1)
                else:
                    when_to_send = now_utc

                self.db.create_user_schedule(
                    user_id=sub_user.id,
                    email=sub_user.email,
                    course_name=course_name,
                    lesson_id=next_lesson,
                    when_to_send=when_to_send,
                )
                logger.info(f"Auto-scheduled lesson {next_lesson} for {sub_user.email} at {when_to_send.isoformat()} (1-day interval).")

        logger.info(f"Successfully generated and persisted Lesson {next_lesson} with {len(saved_exercises)} exercises. Magic link: {magic_link_url}")

        return IngestionResponse(
            status="processed",
            message=f"Lesson {next_lesson} successfully generated with {len(saved_exercises)} exercises.",
            user_id=user.id,
            lesson=next_lesson,
            magic_link_token=magic_link.token,
            magic_link_url=magic_link_url,
            exercise_count=len(saved_exercises),
        )

    def resolve_magic_link(self, token: str) -> MagicLinkResolutionResponse:
        """
        Validates magic link token and retrieves exercises if token is active and user is active.
        """
        magic_link = self.db.get_magic_link_by_token(token)
        if not magic_link:
            return MagicLinkResolutionResponse(
                is_valid=False,
                status="not_found",
            )

        if magic_link.is_revoked:
            return MagicLinkResolutionResponse(
                is_valid=False,
                status="revoked",
                expires_at=magic_link.expires_at,
            )

        if magic_link.is_expired:
            return MagicLinkResolutionResponse(
                is_valid=False,
                status="expired",
                expires_at=magic_link.expires_at,
            )

        # Check User active status
        user = self.db.get_user_by_id(magic_link.user_id)
        if not user or not user.is_active:
            return MagicLinkResolutionResponse(
                is_valid=False,
                status="user_inactive",
                expires_at=magic_link.expires_at,
            )

        # Get Subscription course name
        subscription = self.db.get_subscription_by_id(magic_link.subscription_id)
        course_name = subscription.course_name if subscription else "German Course"

        # Update last_accessed_at timestamp
        self.db.update_magic_link_accessed(token)

        # Fetch exercises bound to this lesson
        exercises = self.db.get_exercises_by_lesson(
            user_id=magic_link.user_id,
            lesson=magic_link.lesson,
            subscription_id=magic_link.subscription_id,
        )

        return MagicLinkResolutionResponse(
            is_valid=True,
            status="active",
            expires_at=magic_link.expires_at,
            lesson=magic_link.lesson,
            course_name=course_name,
            user_name=user.name,
            lesson_exercises=exercises,
        )

    def resolve_user_latest_lesson(
        self, email: str, course_name: Optional[str] = None
    ) -> UserLessonResponse:
        """
        Zero-auth fallback route resolution matching GET /<email>/
        """
        target_course = course_name or settings.default_course_name
        user = self.db.get_user_by_email(email)
        if not user or not user.is_active:
            return UserLessonResponse(
                is_active=False,
                is_subscribed=False,
                status="inactive",
                course_name=target_course,
            )

        subscription = self.db.get_subscription(user.id, target_course)
        if not subscription or not subscription.is_subscribed:
            return UserLessonResponse(
                is_active=True,
                is_subscribed=False,
                status="unsubscribed",
                course_name=target_course,
                user_name=user.name,
            )

        highest_lesson = self.db.get_highest_lesson_number(user.id, subscription.id)
        if highest_lesson <= 0:
            return UserLessonResponse(
                is_active=True,
                is_subscribed=True,
                status="no_lessons",
                course_name=target_course,
                user_name=user.name,
            )

        exercises = self.db.get_exercises_by_lesson(user.id, highest_lesson, subscription.id)

        return UserLessonResponse(
            is_active=True,
            is_subscribed=True,
            status="active",
            lesson=highest_lesson,
            course_name=target_course,
            user_name=user.name,
            lesson_exercises=exercises,
        )

lesson_service = LessonService()
