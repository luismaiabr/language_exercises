import hashlib
import logging
from datetime import date as dt_date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from supabase import Client, create_client

from app.core.config import settings
from app.schemas.db import (
    Answer_db,
    Exercise_db,
    MagicLink_db,
    Subscription_db,
    User_db,
    UserSchedule_db,
)

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        self._client: Optional[Client] = None
        # In-memory storage fallback for local development/testing without live Supabase
        self._mock_users: Dict[str, User_db] = {}  # by id string
        self._mock_subscriptions: Dict[str, Subscription_db] = {}  # by id string
        self._mock_exercises: List[Exercise_db] = []
        self._mock_magic_links: Dict[str, MagicLink_db] = {}  # by token
        self._mock_ingestions: List[Dict[str, Any]] = []
        self._mock_answers: List[Answer_db] = []
        self._mock_user_schedules: List[UserSchedule_db] = []
        self._init_client()

    def _init_client(self):
        url = settings.SUPABASE_URL
        key = settings.SUPABASE_KEY
        is_placeholder = (
            not url
            or "placeholder" in url
            or "your-project" in url
            or not key
            or "placeholder" in key
            or "your-supabase" in key
        )
        if not is_placeholder:
            try:
                self._client = create_client(url, key)
                logger.info("Supabase client initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize live Supabase client ({e}). Using in-memory fallback.")
                self._client = None
        else:
            logger.info("Using local in-memory database mode (Supabase credentials contain placeholders in .env).")
            self._client = None

    @property
    def client(self) -> Optional[Client]:
        return self._client

    # ----------------------------------------------------
    # USERS
    # ----------------------------------------------------
    def get_user_by_email(self, email: str) -> Optional[User_db]:
        email_clean = email.strip().lower()
        if self.client:
            try:
                res = self.client.table("users").select("*").eq("email", email_clean).execute()
                if res.data and len(res.data) > 0:
                    return User_db.model_validate(res.data[0])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase get_user_by_email failed ({e}). Falling back to memory store.")

        for u in self._mock_users.values():
            if u.email.lower() == email_clean:
                return u
        return None

    def get_user_by_id(self, user_id: UUID) -> Optional[User_db]:
        uid_str = str(user_id)
        if self.client:
            try:
                res = self.client.table("users").select("*").eq("id", uid_str).execute()
                if res.data and len(res.data) > 0:
                    return User_db.model_validate(res.data[0])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase get_user_by_id failed ({e}). Falling back to memory store.")

        return self._mock_users.get(uid_str)

    def create_user(self, email: str, name: str, is_active: bool = True) -> User_db:
        email_clean = email.strip().lower()
        if self.client:
            try:
                data = {"email": email_clean, "name": name, "is_active": is_active}
                res = self.client.table("users").insert(data).execute()
                return User_db.model_validate(res.data[0])
            except Exception as e:
                logger.warning(f"Live Supabase create_user failed ({e}). Falling back to memory store.")

        user = User_db(id=uuid4(), email=email_clean, name=name, is_active=is_active)
        self._mock_users[str(user.id)] = user
        return user

    # ----------------------------------------------------
    # SUBSCRIPTIONS
    # ----------------------------------------------------
    def get_subscription(self, user_id: UUID, course_name: str) -> Optional[Subscription_db]:
        uid_str = str(user_id)
        if self.client:
            try:
                res = (
                    self.client.table("subscriptions")
                    .select("*")
                    .eq("user_id", uid_str)
                    .eq("course_name", course_name)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    return Subscription_db.model_validate(res.data[0])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase get_subscription failed ({e}). Falling back to memory store.")

        for sub in self._mock_subscriptions.values():
            if str(sub.user_id) == uid_str and sub.course_name == course_name:
                return sub
        return None

    def get_subscription_by_id(self, subscription_id: UUID) -> Optional[Subscription_db]:
        sid_str = str(subscription_id)
        if self.client:
            try:
                res = self.client.table("subscriptions").select("*").eq("id", sid_str).execute()
                if res.data and len(res.data) > 0:
                    return Subscription_db.model_validate(res.data[0])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase get_subscription_by_id failed ({e}). Falling back to memory store.")

        return self._mock_subscriptions.get(sid_str)

    def create_subscription(self, user_id: UUID, course_name: str, is_subscribed: bool = True) -> Subscription_db:
        uid_str = str(user_id)
        if self.client:
            try:
                data = {"user_id": uid_str, "course_name": course_name, "is_subscribed": is_subscribed}
                res = self.client.table("subscriptions").insert(data).execute()
                return Subscription_db.model_validate(res.data[0])
            except Exception as e:
                logger.warning(f"Live Supabase create_subscription failed ({e}). Falling back to memory store.")

        sub = Subscription_db(id=uuid4(), user_id=user_id, course_name=course_name, is_subscribed=is_subscribed)
        self._mock_subscriptions[str(sub.id)] = sub
        return sub

    def get_all_users(self, only_active: bool = False) -> List[User_db]:
        """Fetch all users, optionally filtering for active users."""
        if self.client:
            try:
                query = self.client.table("users").select("*")
                if only_active:
                    query = query.eq("is_active", True)
                res = query.execute()
                return [User_db.model_validate(row) for row in res.data]
            except Exception as e:
                logger.warning(f"Live Supabase get_all_users failed ({e}). Falling back to memory store.")

        users = list(self._mock_users.values())
        if only_active:
            users = [u for u in users if u.is_active]
        return users

    def is_new_course(self, course_name: str) -> bool:
        """
        Check if course_name is newly introduced (i.e. has no existing subscriptions or exercises).
        """
        course_clean = course_name.strip()
        if self.client:
            try:
                res = self.client.table("subscriptions").select("id").eq("course_name", course_clean).limit(1).execute()
                if res.data and len(res.data) > 0:
                    return False
                return True
            except Exception as e:
                logger.warning(f"Live Supabase is_new_course check failed ({e}). Falling back to memory store.")

        for sub in self._mock_subscriptions.values():
            if sub.course_name.strip() == course_clean:
                return False
        return True

    def get_subscribers_for_course(self, course_name: str, only_active_users: bool = True) -> List[User_db]:
        """
        Fetch all users actively subscribed to course_name.
        """
        course_clean = course_name.strip()
        subscribers: List[User_db] = []
        if self.client:
            try:
                res = (
                    self.client.table("subscriptions")
                    .select("user_id")
                    .eq("course_name", course_clean)
                    .eq("is_subscribed", True)
                    .execute()
                )
                user_ids = [row["user_id"] for row in (res.data or [])]
                for uid in user_ids:
                    user = self.get_user_by_id(UUID(uid))
                    if user and (not only_active_users or user.is_active):
                        subscribers.append(user)
                return subscribers
            except Exception as e:
                logger.warning(f"Live Supabase get_subscribers_for_course failed ({e}). Falling back to memory store.")

        for sub in self._mock_subscriptions.values():
            if sub.course_name.strip() == course_clean and sub.is_subscribed:
                user = self._mock_users.get(str(sub.user_id))
                if user and (not only_active_users or user.is_active):
                    subscribers.append(user)
        return subscribers

    def subscribe_all_users_to_course(self, course_name: str, only_active: bool = False) -> List[Subscription_db]:
        """
        Automatically subscribe all existing users to a new subject/course.
        """
        course_clean = course_name.strip()
        users = self.get_all_users(only_active=only_active)
        created_subs: List[Subscription_db] = []

        for user in users:
            existing = self.get_subscription(user.id, course_clean)
            if not existing:
                sub = self.create_subscription(user_id=user.id, course_name=course_clean, is_subscribed=True)
                created_subs.append(sub)
                logger.info(f"Auto-subscribed user {user.email} to new subject '{course_clean}'.")
            elif not existing.is_subscribed:
                # Reactivate subscription if it was inactive
                if self.client:
                    try:
                        self.client.table("subscriptions").update({"is_subscribed": True}).eq("id", str(existing.id)).execute()
                        existing.is_subscribed = True
                    except Exception as e:
                        logger.warning(f"Failed to update subscription in live Supabase: {e}")
                existing.is_subscribed = True
                created_subs.append(existing)

        return created_subs

    # ----------------------------------------------------
    # EXERCISES
    # ----------------------------------------------------
    def get_highest_lesson_number(self, user_id: UUID, subscription_id: Optional[UUID]) -> int:
        uid_str = str(user_id)
        if self.client:
            try:
                query = (
                    self.client.table("exercises")
                    .select("lesson")
                    .eq("user_id", uid_str)
                    .order("lesson", desc=True)
                    .limit(1)
                )
                if subscription_id:
                    query = query.eq("subscription_id", str(subscription_id))
                res = query.execute()
                if res.data and len(res.data) > 0:
                    return int(res.data[0]["lesson"])
                return 0
            except Exception as e:
                logger.warning(f"Live Supabase get_highest_lesson_number failed ({e}). Falling back to memory store.")

        max_lesson = 0
        for ex in self._mock_exercises:
            if str(ex.user_id) == uid_str:
                if subscription_id is None or (ex.subscription_id and str(ex.subscription_id) == str(subscription_id)):
                    if ex.lesson > max_lesson:
                        max_lesson = ex.lesson
        return max_lesson

    def save_exercises(self, exercises: List[Dict[str, Any]]) -> List[Exercise_db]:
        if self.client:
            try:
                cleaned = []
                for e in exercises:
                    item = dict(e)
                    if "id" in item:
                        item["id"] = str(item["id"])
                    if "user_id" in item:
                        item["user_id"] = str(item["user_id"])
                    if "subscription_id" in item and item["subscription_id"]:
                        item["subscription_id"] = str(item["subscription_id"])
                    if "date" in item and isinstance(item["date"], (dt_date, datetime)):
                        item["date"] = item["date"].isoformat()
                    cleaned.append(item)

                res = self.client.table("exercises").insert(cleaned).execute()
                return [Exercise_db.model_validate(row) for row in res.data]
            except Exception as e:
                logger.warning(f"Live Supabase save_exercises failed ({e}). Falling back to memory store.")

        saved = []
        for e in exercises:
            model = Exercise_db.model_validate(e)
            self._mock_exercises.append(model)
            saved.append(model)
        return saved

    def get_exercises_by_lesson(
        self, user_id: UUID, lesson: int, subscription_id: Optional[UUID] = None
    ) -> List[Exercise_db]:
        uid_str = str(user_id)
        if self.client:
            try:
                query = (
                    self.client.table("exercises")
                    .select("*")
                    .eq("user_id", uid_str)
                    .eq("lesson", lesson)
                    .order("created_at", desc=False)
                )
                if subscription_id:
                    query = query.eq("subscription_id", str(subscription_id))
                res = query.execute()
                return [Exercise_db.model_validate(row) for row in res.data]
            except Exception as e:
                logger.warning(f"Live Supabase get_exercises_by_lesson failed ({e}). Falling back to memory store.")

        results = []
        for ex in self._mock_exercises:
            if str(ex.user_id) == uid_str and ex.lesson == lesson:
                if subscription_id is None or (ex.subscription_id and str(ex.subscription_id) == str(subscription_id)):
                    results.append(ex)
        return results

    def get_exercise_by_id(self, exercise_id: UUID) -> Optional[Exercise_db]:
        eid_str = str(exercise_id)
        if self.client:
            try:
                res = self.client.table("exercises").select("*").eq("id", eid_str).execute()
                if res.data and len(res.data) > 0:
                    return Exercise_db.model_validate(res.data[0])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase get_exercise_by_id failed ({e}). Falling back to memory store.")

        for ex in self._mock_exercises:
            if str(ex.id) == eid_str:
                return ex
        return None

    # ----------------------------------------------------
    # MAGIC LINKS
    # ----------------------------------------------------
    def create_magic_link(
        self, user_id: UUID, subscription_id: UUID, lesson: int, timespan_days: Optional[int] = None
    ) -> MagicLink_db:
        days = timespan_days if timespan_days is not None else settings.magic_link_timespan_days
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=days)

        magic_link = MagicLink_db(
            id=uuid4(),
            user_id=user_id,
            subscription_id=subscription_id,
            lesson=lesson,
            created_at=now,
            expires_at=expires_at,
        )

        if self.client:
            try:
                data = {
                    "id": str(magic_link.id),
                    "token": magic_link.token,
                    "user_id": str(magic_link.user_id),
                    "subscription_id": str(magic_link.subscription_id),
                    "lesson": magic_link.lesson,
                    "created_at": magic_link.created_at.isoformat(),
                    "expires_at": magic_link.expires_at.isoformat(),
                    "is_revoked": magic_link.is_revoked,
                }
                res = self.client.table("magic_links").insert(data).execute()
                return MagicLink_db.model_validate(res.data[0])
            except Exception as e:
                logger.warning(f"Live Supabase create_magic_link failed ({e}). Falling back to memory store.")

        self._mock_magic_links[magic_link.token] = magic_link
        return magic_link

    def get_magic_link_by_token(self, token: str) -> Optional[MagicLink_db]:
        if self.client:
            try:
                res = self.client.table("magic_links").select("*").eq("token", token).execute()
                if res.data and len(res.data) > 0:
                    return MagicLink_db.model_validate(res.data[0])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase get_magic_link_by_token failed ({e}). Falling back to memory store.")

        return self._mock_magic_links.get(token)

    def update_magic_link_accessed(self, token: str):
        now = datetime.now(timezone.utc)
        if self.client:
            try:
                self.client.table("magic_links").update({"last_accessed_at": now.isoformat()}).eq("token", token).execute()
            except Exception as e:
                logger.warning(f"Could not update last_accessed_at in Supabase for token {token}: {e}")

        if token in self._mock_magic_links:
            self._mock_magic_links[token].last_accessed_at = now

    # ----------------------------------------------------
    # IDEMPOTENCY / INGESTION LEDGER
    # ----------------------------------------------------
    def calculate_text_hash(self, email: str, course_name: str, raw_text: str) -> str:
        content = f"{email.strip().lower()}||{course_name.strip()}||{raw_text.strip()}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def check_existing_ingestion(self, user_id: UUID, course_name: str, text_hash: str) -> Optional[int]:
        uid_str = str(user_id)
        if self.client:
            try:
                res = (
                    self.client.table("lesson_ingestions")
                    .select("lesson")
                    .eq("user_id", uid_str)
                    .eq("course_name", course_name)
                    .eq("text_hash", text_hash)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    return int(res.data[0]["lesson"])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase check_existing_ingestion failed ({e}). Falling back to memory store.")

        for row in self._mock_ingestions:
            if row["user_id"] == uid_str and row["course_name"] == course_name and row["text_hash"] == text_hash:
                return int(row["lesson"])
        return None

    def record_ingestion(self, user_id: UUID, course_name: str, text_hash: str, lesson: int):
        uid_str = str(user_id)
        if self.client:
            try:
                data = {
                    "user_id": uid_str,
                    "course_name": course_name,
                    "text_hash": text_hash,
                    "lesson": lesson,
                }
                self.client.table("lesson_ingestions").insert(data).execute()
                return
            except Exception as e:
                logger.warning(f"Could not record ingestion ledger in Supabase: {e}")

        self._mock_ingestions.append({
            "user_id": uid_str,
            "course_name": course_name,
            "text_hash": text_hash,
            "lesson": lesson,
        })

    # ----------------------------------------------------
    # ANSWERS
    # ----------------------------------------------------
    def record_answer(
        self,
        exercise_id: UUID,
        user_id: UUID,
        lesson: int,
        exercise_type: str,
        answer: str,
        submission_date: Optional[dt_date] = None,
    ) -> Answer_db:
        sub_date = submission_date or dt_date.today()
        record = Answer_db(
            id=uuid4(),
            exercise_id=exercise_id,
            user_id=user_id,
            date=sub_date,
            lesson=lesson,
            exercise_type=exercise_type,  # type: ignore
            answer=answer,
        )
        if self.client:
            try:
                data = {
                    "id": str(record.id),
                    "exercise_id": str(record.exercise_id),
                    "user_id": str(record.user_id),
                    "date": record.date.isoformat(),
                    "lesson": record.lesson,
                    "exercise_type": record.exercise_type,
                    "answer": record.answer,
                    "created_at": record.created_at.isoformat(),
                }
                res = self.client.table("answers").insert(data).execute()
                return Answer_db.model_validate(res.data[0])
            except Exception as e:
                logger.warning(f"Live Supabase record_answer failed ({e}). Falling back to memory store.")

        self._mock_answers.append(record)
        return record

    # ----------------------------------------------------
    # USER SCHEDULES (language_exercises_scheduler)
    # ----------------------------------------------------
    def get_latest_schedule_for_user(
        self, user_id: UUID, course_name: str
    ) -> Optional[UserSchedule_db]:
        """
        Fetch the most recently scheduled lesson for this user and course.
        """
        uid_str = str(user_id)
        course_clean = course_name.strip()
        if self.client:
            try:
                res = (
                    self.client.table("user_schedules")
                    .select("*")
                    .eq("user_id", uid_str)
                    .eq("course_name", course_clean)
                    .order("when_to_send", desc=True)
                    .limit(1)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    return UserSchedule_db.model_validate(res.data[0])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase get_latest_schedule_for_user failed ({e}). Falling back to memory store.")

        matching = [
            s for s in self._mock_user_schedules
            if str(s.user_id) == uid_str and s.course_name == course_clean
        ]
        if not matching:
            return None
        matching.sort(key=lambda s: s.when_to_send, reverse=True)
        return matching[0]

    def get_user_schedule(
        self, user_id: UUID, course_name: str, lesson_id: int
    ) -> Optional[UserSchedule_db]:
        """
        Find an existing schedule for a specific user, course, and lesson.
        """
        uid_str = str(user_id)
        course_clean = course_name.strip()
        if self.client:
            try:
                res = (
                    self.client.table("user_schedules")
                    .select("*")
                    .eq("user_id", uid_str)
                    .eq("course_name", course_clean)
                    .eq("lesson_id", lesson_id)
                    .limit(1)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    return UserSchedule_db.model_validate(res.data[0])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase get_user_schedule failed ({e}). Falling back to memory store.")

        for s in self._mock_user_schedules:
            if str(s.user_id) == uid_str and s.course_name == course_clean and s.lesson_id == lesson_id:
                return s
        return None

    def create_user_schedule(
        self,
        user_id: UUID,
        email: str,
        course_name: str,
        lesson_id: int,
        when_to_send: datetime,
    ) -> UserSchedule_db:
        """
        Schedule a lesson email for a user at when_to_send.
        """
        schedule = UserSchedule_db(
            id=uuid4(),
            user_id=user_id,
            email=email.strip().lower(),
            course_name=course_name.strip(),
            lesson_id=lesson_id,
            when_to_send=when_to_send,
            status="pending",
        )

        if self.client:
            try:
                data = {
                    "id": str(schedule.id),
                    "user_id": str(schedule.user_id),
                    "email": schedule.email,
                    "course_name": schedule.course_name,
                    "lesson_id": schedule.lesson_id,
                    "when_to_send": schedule.when_to_send.isoformat(),
                    "status": schedule.status,
                    "created_at": schedule.created_at.isoformat(),
                }
                res = self.client.table("user_schedules").insert(data).execute()
                return UserSchedule_db.model_validate(res.data[0])
            except Exception as e:
                logger.warning(f"Live Supabase create_user_schedule failed ({e}). Falling back to memory store.")

        self._mock_user_schedules.append(schedule)
        return schedule

    def get_due_schedules(self, target_time: Optional[datetime] = None) -> List[UserSchedule_db]:
        """
        Retrieve all pending schedules whose when_to_send <= target_time (default now).
        """
        now = target_time or datetime.now(timezone.utc)
        if self.client:
            try:
                res = (
                    self.client.table("user_schedules")
                    .select("*")
                    .eq("status", "pending")
                    .lte("when_to_send", now.isoformat())
                    .order("when_to_send", desc=False)
                    .execute()
                )
                return [UserSchedule_db.model_validate(row) for row in res.data]
            except Exception as e:
                logger.warning(f"Live Supabase get_due_schedules failed ({e}). Falling back to memory store.")

        due = []
        for s in self._mock_user_schedules:
            if s.status == "pending":
                s_time = s.when_to_send if s.when_to_send.tzinfo else s.when_to_send.replace(tzinfo=timezone.utc)
                if s_time <= now:
                    due.append(s)
        due.sort(key=lambda s: s.when_to_send)
        return due

    def update_schedule_status(
        self,
        schedule_id: UUID,
        status: str,
        sent_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> Optional[UserSchedule_db]:
        """
        Update the status (sent, failed, etc.) of a user schedule.
        """
        sid_str = str(schedule_id)
        now = sent_at or datetime.now(timezone.utc)

        if self.client:
            try:
                data = {"status": status}
                if status == "sent":
                    data["sent_at"] = now.isoformat()
                if error_message:
                    data["error_message"] = error_message
                res = self.client.table("user_schedules").update(data).eq("id", sid_str).execute()
                if res.data and len(res.data) > 0:
                    return UserSchedule_db.model_validate(res.data[0])
                return None
            except Exception as e:
                logger.warning(f"Live Supabase update_schedule_status failed ({e}). Falling back to memory store.")

        for s in self._mock_user_schedules:
            if str(s.id) == sid_str:
                s.status = status  # type: ignore
                if status == "sent":
                    s.sent_at = now
                if error_message:
                    s.error_message = error_message
                return s
        return None

supabase_service = SupabaseService()
