import asyncio
from datetime import date as dt_date, datetime, timedelta, timezone
from uuid import uuid4
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.db.supabase_client import supabase_service
from app.schemas.api import DynamicWrittenEvaluationRequest, WebhookIngestionPayload
from app.schemas.exercise import ChoiceOption, MultipleChoiceExercise, WrittenExercise
from app.services.lesson_service import lesson_service
from app.services.ai_service import ai_service

def test_config_files_loaded():
    """Verify that config YAML files are loaded and not relying exclusively on .env."""
    assert settings.app_name == "German Exercise Platform"
    assert settings.server_port == 8000
    assert settings.magic_link_timespan_days == 7
    assert settings.openrouter_model == "google/gemini-2.5-flash"
    assert "lesson_generation" in settings.prompts
    assert "written_evaluation" in settings.prompts

def test_auto_provisioning_inactive_user():
    """Verify section 2.2: User not yet in users table is created with is_active = False and skipped."""
    email = f"student_{uuid4().hex[:8]}@example.com"
    payload = WebhookIngestionPayload(
        email=email,
        course_name="German Theory",
        raw_text="Heute lernen wir den Akkusativ mit Präpositionen: durch, für, gegen, ohne, um.",
    )
    result = asyncio.run(lesson_service.ingest_webhook_lesson(payload))
    assert result.status == "skipped_inactive"
    assert result.user_id is not None

    # Check user in DB
    user = supabase_service.get_user_by_id(result.user_id)
    assert user is not None
    assert user.is_active is False

def test_active_user_lesson_generation_and_idempotency():
    """Verify active user lesson generation, sequential numbering, and idempotency."""
    email = f"active_student_{uuid4().hex[:8]}@example.com"
    # Create active user
    user = supabase_service.create_user(email=email, name="Hans Schmidt", is_active=True)
    sub = supabase_service.create_subscription(user.id, "German Theory", is_subscribed=True)

    raw_text = "Die Wechselpräpositionen verlangen Akkusativ bei Bewegung (Wohin?) und Dativ bei Stillstand (Wo?)."
    payload = WebhookIngestionPayload(
        email=email,
        course_name="German Theory",
        raw_text=raw_text,
    )

    # 1. First Ingestion
    res1 = asyncio.run(lesson_service.ingest_webhook_lesson(payload))
    assert res1.status == "processed"
    assert res1.lesson == 1
    assert res1.magic_link_token is not None
    assert res1.magic_link_url is not None

    # 2. Duplicate Ingestion (Idempotency test)
    res2 = asyncio.run(lesson_service.ingest_webhook_lesson(payload))
    assert res2.status == "duplicate"
    assert res2.lesson == 1

    # 3. New lesson text -> Sequential Lesson 2
    payload2 = WebhookIngestionPayload(
        email=email,
        course_name="German Theory",
        raw_text="Zweite Lektion: Perfekt mit haben und sein. Verben der Ortsveränderung nutzen sein.",
    )
    res3 = asyncio.run(lesson_service.ingest_webhook_lesson(payload2))
    assert res3.status == "processed"
    assert res3.lesson == 2

def test_magic_link_resolution():
    """Verify resolving magic link token returns exercises and enforces expiration."""
    user = supabase_service.create_user(email=f"ml_{uuid4().hex[:8]}@test.de", name="Greta", is_active=True)
    sub = supabase_service.create_subscription(user.id, "German Theory", is_subscribed=True)
    
    # Create magic link
    ml = supabase_service.create_magic_link(user.id, sub.id, lesson=1, timespan_days=7)
    
    # Save a mock exercise
    supabase_service.save_exercises([{
        "user_id": user.id,
        "subscription_id": sub.id,
        "lesson": 1,
        "exercise_type": "written",
        "question": "Translate: The cat sits on the table.",
        "theory_summary": "Prepositions and cases summary.",
    }])

    # Resolve token
    resolution = lesson_service.resolve_magic_link(ml.token)
    assert resolution.is_valid is True
    assert resolution.status == "active"
    assert resolution.lesson == 1
    assert len(resolution.lesson_exercises) >= 1

    # Test expired token
    expired_ml = supabase_service.create_magic_link(user.id, sub.id, lesson=1, timespan_days=-1)
    exp_resolution = lesson_service.resolve_magic_link(expired_ml.token)
    assert exp_resolution.is_valid is False
    assert exp_resolution.status == "expired"

def test_written_exercise_evaluation():
    """Verify dynamic AI evaluation of written exercises."""
    eval_res = asyncio.run(
        ai_service.evaluate_written_answer(
            question_prompt="The boy runs into the garden.",
            theory_summary="Akkusativ for movement into a location: in den Garten.",
            user_answer="Der Junge läuft in den Garten.",
        )
    )
    assert eval_res.is_correct is True
    assert len(eval_res.explanation) > 0

if __name__ == "__main__":
    print("Running backend tests...")
    test_config_files_loaded()
    print("[OK] Config files test passed.")
    test_auto_provisioning_inactive_user()
    print("[OK] Auto-provisioning test passed.")
    test_active_user_lesson_generation_and_idempotency()
    print("[OK] Lesson generation, sequential numbering & idempotency test passed.")
    test_magic_link_resolution()
    print("[OK] Magic link resolution & expiration test passed.")
    test_written_exercise_evaluation()
    print("[OK] Written exercise dynamic evaluation test passed.")
    print("ALL TESTS PASSED SUCCESSFULLY!")
