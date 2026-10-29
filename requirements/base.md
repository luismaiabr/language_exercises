# System Requirements Specification: AI-Driven German Exercise Platform

## 1. System Overview
A lightweight, zero-authentication web application designed to receive raw German lesson text (the theory email) from n8n, generate the exercises in the backend with an AI model, store them in a Supabase (PostgreSQL) database, and serve them to users via a personalized URL path (`/<email>/`). The system evaluates multiple-choice exercises instantaneously on the client side using pre-calculated explanations, while written exercises are evaluated dynamically at runtime by an AI agent via the backend.

---

## 2. Functional Requirements

### 2.1. Zero-Auth Access & Subscription Routing
* **Route Resolution:** The frontend and backend must resolve routes matching `GET /<email>/` (e.g., `domain.com/student@example.com/`). No login, session tokens, or password verification are required.
* **User & Subscription Validation:** Upon receiving a request for `/<email>/`, the backend must query Supabase to verify:
  1. The user exists in the `users` table and `is_active` is `True`.
  2. The user has a corresponding record in the `subscriptions` table where `is_subscribed` is `True` for the target course (e.g., `course_name = "German Theory"`).
* **Latest Lesson Resolution:** If validation passes, the system queries the `exercises` table for that `user_id` and subscription, selects the highest `lesson` number, and returns all exercises in that lesson.
* **Empty/Inactive States:** If the user is inactive, unsubscribed, or has no lessons generated yet, the UI renders a clean, localized state indicating the status.

### 2.2. Webhook Ingestion & Backend Lesson Generation (Internal API)
* **Endpoint:** `POST /api/webhooks/n8n/lessons` protected via a static `X-API-Key` header.
* **Responsibility Split:**
  * **n8n (transport only):** Triggered daily when the user receives their theoretical German email. n8n only extracts the recipient `email` and the raw lesson text from the email body and forwards them to this endpoint. n8n performs **no** AI calls, exercise generation, or database writes.
  * **Backend (`language_exercises`):** Owns all lesson generation. It receives the raw text, builds the prompt, calls the AI model (OpenRouter) to generate the `theory_summary` and the exercises (multiple-choice with per-option explanations, and written prompts), validates the result against the `Exercise` Pydantic schemas, assigns the next sequential `lesson` number for the user and course, persists the rows in Supabase, and creates the magic link.
* **Processing:** Generation may run as a background task; the endpoint responds `202 Accepted` quickly so n8n is not blocked. Invalid or unparseable AI output is retried a bounded number of times, then logged and rejected with an error status so n8n can surface the failure.
* **Idempotency:** Re-sending the same email text for the same user and course must not create a duplicate lesson (e.g., deduplicate via a hash of the raw text).
* **Auto-Provisioning (Inactive by Default):** If an email arrives for a user not yet in the `users` table, the backend creates the user with `is_active = False` (and a matching subscription record), and does not generate any exercises. The user must be activated manually (or by a separate process) before receiving lessons.
* **Active-Only Generation:** Lesson generation (AI call, exercise persistence, lesson numbering, magic link creation) runs only when the user exists, `is_active` is `True`, and the subscription for the course has `is_subscribed = True`. Otherwise the backend skips generation, stores nothing beyond the provisioning above, and responds with a non-generating status (e.g., `202 Accepted` with `status: "skipped_inactive"`) so n8n does not treat it as a failure. Raw text from inactive users is not retained, so lessons are not back-filled on activation.

### 2.3. Exercise Evaluation & Feedback Engine
* **Multiple Choice (Pre-Calculated & Instantaneous):**
  * Evaluated 100% client-side with zero latency.
  * The JSON payload contains an array of options, each binding its own boolean `is_correct` flag and a specific `explanation`.
  * When the user selects an option, the UI immediately reveals whether it is right or wrong. If wrong, it displays why that specific choice fails and highlights the correct option alongside its explanation.
* **Written Exercises (100% Dynamic Runtime AI Evaluation):**
  * The database stores **only** the `question` prompt (and optional grammar context). No `expected_answer` or `correct_explanation` is pre-calculated.
  * When the user submits their written string, the UI displays a rotating loading arch and dispatches a `POST /api/exercises/evaluate-written` request to the backend.
  * The backend forwards the `question`, `theory_summary` (for context), and the user's `user_answer` to the AI model (OpenRouter).
  * The AI evaluates the input and returns `is_correct` (`bool`) and `explanation` (`str`).
    * If `is_correct == True`: The explanation validates why the user's construction/vocabulary is accurate (and notes any alternative natural phrasing if applicable).
    * If `is_correct == False`: The explanation details the grammatical or lexical mistake and explicitly provides the correct German answer.

---

## 3. Technical & UI Requirements

* **Backend Stack:** Python 3.11+ with FastAPI and Pydantic V2.
* **Database:** Supabase (PostgreSQL). Uses normalized `exercises` and `answers` tables, paired with relational integrity (`FOREIGN KEY`) across `users` and `subscriptions`.
* **UI Aesthetic:** High-contrast monochromatic palette:
  * **Backgrounds:** Deep Black (`#0A0A0A`) and Dark Charcoal (`#141414`).
  * **Typography:** Crisp Off-White (`#F5F5F5`) and Muted Gray (`#A3A3A3`).
  * **Accents:** Cyan (`#00E5FF`) for active focus, interactive borders, and the rotating loading arch; Gold (`#FFD700`) for mastery/score highlights.
  * **Strict Constraint:** Zero purple or neon-pink/green tones.

---

## 4. Database Architecture (Supabase / PostgreSQL)

To maintain data integrity and performance in Supabase, the schema requires four core tables (`users`, `subscriptions`, `exercises`, and `answers`), enhanced with UUID primary keys, indexes on lookup fields, and unique constraints:

1. **`users` Table:**
   * `id` (`UUID`, Primary Key, Default: `gen_random_uuid()`)
   * `email` (`VARCHAR`, Unique, Indexed, Not Null) — *Critical lookup key for URL routing.*
   * `name` (`VARCHAR`, Not Null)
   * `is_active` (`BOOLEAN`, Default: `True`, Not Null)
   * `created_at` (`TIMESTAMPTZ`, Default: `now()`)

2. **`subscriptions` Table:**
   * `id` (`UUID`, Primary Key, Default: `gen_random_uuid()`)
   * `user_id` (`UUID`, Foreign Key -> `users.id` ON DELETE CASCADE, Not Null)
   * `course_name` (`VARCHAR`, Not Null, e.g., `"German Daily Theory"`)
   * `is_subscribed` (`BOOLEAN`, Default: `True`, Not Null)
   * `updated_at` (`TIMESTAMPTZ`, Default: `now()`)
   * *Constraint:* `UNIQUE(user_id, course_name)` to prevent duplicate course rows per user.

3. **`exercises` Table:**
   * `id` (`UUID`, Primary Key, Default: `gen_random_uuid()`)
   * `user_id` (`UUID`, Foreign Key -> `users.id` ON DELETE CASCADE, Not Null)
   * `subscription_id` (`UUID`, Foreign Key -> `subscriptions.id` ON DELETE SET NULL, Nullable)
   * `date` (`DATE`, Not Null, Default: `CURRENT_DATE`, Indexed) — *Publication or class date.*
   * `lesson` (`INTEGER`, Not Null) — *Stable, sequential lesson number for this user and course.*
   * `exercise_type` (`VARCHAR`, Not Null) — *For example, `multiple_choice` or `written`.*
   * `question` (`TEXT`, Not Null)
   * `options` (`JSONB`, Nullable) — *Optional choices for multiple-choice exercises; null for written exercises.*
   * `theory_summary` (`TEXT`, Nullable) — *Context passed to the AI during written evaluation.*
   * `created_at` (`TIMESTAMPTZ`, Default: `now()`)
   * *Constraints:* `CHECK (lesson > 0)` and `UNIQUE(id, user_id)` for composite answer ownership validation. If a separate exercise sequence is required, the ingestion process must provide a stable exercise identifier.
   * *Indexes:* `INDEX(user_id, subscription_id, lesson)` and `INDEX(user_id, date)`.

4. **`answers` Table:**
   * `id` (`UUID`, Primary Key, Default: `gen_random_uuid()`)
   * `exercise_id` (`UUID`, Foreign Key -> `exercises.id` ON DELETE CASCADE, Not Null)
   * `user_id` (`UUID`, Foreign Key -> `users.id` ON DELETE CASCADE, Not Null)
   * `date` (`DATE`, Not Null) — *Date on which the answer was submitted.*
   * `lesson` (`INTEGER`, Not Null) — *Copied from the exercise to support lesson-level reporting.*
   * `exercise_type` (`VARCHAR`, Not Null) — *Copied from the exercise for reporting and validation.*
   * `answer` (`TEXT`, Not Null) — *The selected option text or submitted written response.*
   * `created_at` (`TIMESTAMPTZ`, Default: `now()`)
   * *Constraints:* `CHECK (lesson > 0)` and composite `FOREIGN KEY(exercise_id, user_id) REFERENCES exercises(id, user_id)` so an answer cannot be recorded for another user's exercise. Multiple rows are allowed when answer history and retries are required.
   * *Indexes:* `INDEX(user_id, lesson)` and `INDEX(exercise_id, created_at)`.

### 4.1. Lesson Identification

Use the **lesson number** as the canonical lesson identifier and retain `date` as lesson metadata.

* A lesson number is stable even when an email is delayed, regenerated, or imported after the day it was created.
* Dates are not guaranteed to be unique: a lesson may be corrected or retried on the same date, and users in different time zones may cross a date boundary.
* The ingestion process must assign a positive, sequential `lesson` number per user and course. The application must not infer the lesson number from the calendar date.
* `date` remains indexed for scheduling, display, and queries such as “latest published lesson.” When two records have the same date, resolve ties by the highest `lesson` number and then `created_at`.
* Answers should reference `exercise_id`; their copied `date`, `lesson`, and `exercise_type` values are denormalized reporting fields and must be validated against the referenced exercise on write.

The latest lesson query should therefore select the highest lesson number for the user and subscription, rather than relying only on a date:

```sql
SELECT lesson
FROM exercises
WHERE user_id = :user_id
  AND subscription_id IS NOT DISTINCT FROM :subscription_id
GROUP BY lesson
ORDER BY lesson DESC
LIMIT 1;
```

---

## 5. Pydantic V2 Schemas (Domain, API & Database Models)

```python
from datetime import date as dt_date, datetime
from typing import Annotated, List, Literal, Optional, Union
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, EmailStr, Field

# ==========================================
# 1. EXERCISE CONTENT SCHEMAS
# ==========================================

class ChoiceOption(BaseModel):
    text: str = Field(..., description="The option text displayed to the user.")
    is_correct: bool = Field(..., description="True if this is the right answer.")
    explanation: str = Field(
        ..., 
        description="Pre-calculated explanation of why this specific option is correct or why it is wrong and what the right rule is."
    )

class MultipleChoiceExercise(BaseModel):
    exercise_type: Literal["multiple_choice"] = "multiple_choice"
    question: str = Field(..., description="The German question or fill-in-the-blank prompt.")
    options: List[ChoiceOption] = Field(
        ..., 
        min_length=2, 
        description="Pre-calculated options with instantaneous feedback."
    )

class WrittenExercise(BaseModel):
    exercise_type: Literal["written"] = "written"
    question: str = Field(
        ..., 
        description="The open prompt for the user (e.g., 'Translate into German: ...' or 'Rewrite in Perfekt: ...')."
    )
    # No expected_answer or correct_explanation stored here.
    # Evaluated dynamically by AI at the exact moment the user submits an answer.

Exercise = Annotated[
    Union[MultipleChoiceExercise, WrittenExercise], 
    Field(discriminator="exercise_type")
]


# ==========================================
# 2. SUPABASE DATABASE MODELS (*_db)
# ==========================================

class User_db(BaseModel):
    """Represents a row in the Supabase 'users' table."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Primary Key (UUID).")
    email: EmailStr = Field(..., description="Critical unique identifier used in /<email>/ routing.")
    name: str = Field(..., min_length=1, description="Full name or alias of the student.")
    is_active: bool = Field(default=True, description="Global kill-switch for user access.")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Subscription_db(BaseModel):
    """Represents a row in the Supabase 'subscriptions' table."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4, description="Primary Key (UUID).")
    user_id: UUID = Field(..., description="Foreign Key referencing users.id.")
    course_name: str = Field(..., description="Identifier of the email course, e.g., 'German Theory'.")
    is_subscribed: bool = Field(default=True, description="Whether the user actively receives/accesses lessons.")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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
    created_at: datetime = Field(default_factory=datetime.utcnow)

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
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ==========================================
# 3. API REQUEST & RESPONSE PAYLOADS
# ==========================================

class WebhookIngestionPayload(BaseModel):
    """Payload sent by n8n: only the recipient and the raw lesson text.
    The backend generates the exercises, theory_summary and lesson number."""
    email: EmailStr
    course_name: str = "German Theory"
    date: dt_date = Field(default_factory=dt_date.today)
    raw_text: str = Field(..., min_length=1, description="Raw lesson (theory email) text.")

class GeneratedLesson(BaseModel):
    """Structured output the backend requires from the AI model."""
    theory_summary: str
    exercises: List[Exercise] = Field(..., min_length=1)

class WrittenEvaluationRequest(BaseModel):
    """Payload sent by the frontend when the user submits a written answer."""
    exercise_id: UUID = Field(..., description="ID of the Exercise_db row for context lookup.")
    question_prompt: str = Field(..., description="The specific WrittenExercise.question text.")
    user_answer: str = Field(..., min_length=1, description="The raw text typed by the user.")

class WrittenEvaluationResponse(BaseModel):
    """Real-time AI evaluation returned to the frontend while the loading arch spins."""
    is_correct: bool = Field(
        ..., 
        description="True if the user's German answer is grammatically and semantically valid."
    )
    explanation: str = Field(
        ..., 
        description="If correct: explains why it works. If incorrect: explains the error and states the exact correct answer."
    )

### Additional Requirement 1: Ephemeral Magic Link Authentication & Token Lifecycle

#### 1. Scope & Security Model
To eliminate credentials without exposing plaintext emails or static URLs, each daily lesson run is authenticated through an expiring capability URL (Magic Link) embedded directly into the notification email or generated via n8n.
* **Route Structure:** `GET /lesson/{token}` (replaces `GET /{email}/`).
* **Format:** A cryptographically secure, high-entropy URL-safe string generated using `secrets.token_urlsafe(32)` (or an HMAC-SHA256 signed payload).
* **Referer Suppression:** The frontend HTML must enforce `<meta name="referrer" content="no-referrer">` to eliminate token leakage if external reference links are followed.

#### 2. Expiration & Timespan Policy
* **Configurable Lifespan:** The magic link remains valid for `<MAGIC_LINK_TIMESPAN>` days from its issuance (`created_at`).
* **Validation Logic:** 
  $$\text{valid} \iff (\text{current\_time} \le \text{expires\_at}) \land (\text{is\_revoked} == \text{False}) \land (\text{user.is\_active} == \text{True})$$
* **Expired State Handling:** If accessed past expiration, the UI must intercept the token and display an HTTP 410 Gone / Session Expired state (styled with the monochromatic palette and cyan accents) with no option to submit answers or trigger the dynamic AI evaluator.

#### 3. Database Layer Additions (Supabase / PostgreSQL)

A dedicated `magic_links` table is added to decouple authentication from the primary entity tables and allow per-link revocation and auditing:

* **`magic_links` Table:**
  * `id` (`UUID`, Primary Key, Default: `gen_random_uuid()`)
  * `token` (`VARCHAR(64)`, Unique, Indexed, Not Null) — *The capability key in the URL path.*
  * `user_id` (`UUID`, Foreign Key -> `users.id` ON DELETE CASCADE, Not Null)
  * `subscription_id` (`UUID`, Foreign Key -> `subscriptions.id` ON DELETE CASCADE, Not Null)
  * `lesson` (`INTEGER`, Not Null) — *Directly binds the token to that specific daily lesson.*
  * `created_at` (`TIMESTAMPTZ`, Default: `now()`, Not Null)
  * `expires_at` (`TIMESTAMPTZ`, Not Null) — *Calculated as `created_at + INTERVAL '<MAGIC_LINK_TIMESPAN> days'`.*
  * `is_revoked` (`BOOLEAN`, Default: `False`, Not Null)
  * `last_accessed_at` (`TIMESTAMPTZ`, Nullable)

#### 4. Pydantic V2 Schemas for Magic Link System

```python
from datetime import datetime, timedelta
import secrets
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

# Configurable environment / system constant
MAGIC_LINK_TIMESPAN_DAYS: int = 7  # Default fallback; overridden by <MAGIC_LINK_TIMESPAN>

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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=MAGIC_LINK_TIMESPAN_DAYS),
        description="Expiration timestamp calculated using MAGIC_LINK_TIMESPAN."
    )
    is_revoked: bool = Field(default=False, description="Manual revocation flag.")
    last_accessed_at: Optional[datetime] = Field(default=None)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return (not self.is_revoked) and (not self.is_expired)

class MagicLinkResolutionResponse(BaseModel):
    """Payload delivered to frontend when opening /lesson/{token}."""
    is_valid: bool
    status: str = Field(..., description="'active', 'expired', or 'revoked'")
    expires_at: datetime
    lesson_exercises: Optional[List[Exercise_db]] = Field(
        default=None,
        description="The exercises in the bound lesson if the token is valid."
    )

class DynamicWrittenEvaluationRequest(BaseModel):
    """Protected written answer evaluation requiring the valid token."""
    token: str = Field(..., description="The magic link token passed from the client session.")
    question_prompt: str = Field(..., description="Prompt of the written exercise.")
    user_answer: str = Field(..., min_length=1)