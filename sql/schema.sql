-- ====================================================================
-- AI-Driven German Exercise Platform: Supabase PostgreSQL Schema
-- Based on requirements in language_exercises/requirements/base.md
-- ====================================================================

-- 1. Enable pgcrypto / uuid-ossp for UUID generation if not already active
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 3. SUBSCRIPTIONS TABLE
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_name VARCHAR(100) NOT NULL,
    is_subscribed BOOLEAN DEFAULT TRUE NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_subscriptions_user_course UNIQUE (user_id, course_name)
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);

-- 4. EXERCISES TABLE
CREATE TABLE IF NOT EXISTS exercises (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    lesson INTEGER NOT NULL CHECK (lesson > 0),
    exercise_type VARCHAR(50) NOT NULL CHECK (exercise_type IN ('multiple_choice', 'written')),
    question TEXT NOT NULL,
    options JSONB DEFAULT NULL,
    theory_summary TEXT DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_exercises_id_user UNIQUE (id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_exercises_user_sub_lesson ON exercises(user_id, subscription_id, lesson);
CREATE INDEX IF NOT EXISTS idx_exercises_user_date ON exercises(user_id, date);

-- 5. ANSWERS TABLE
CREATE TABLE IF NOT EXISTS answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exercise_id UUID NOT NULL,
    user_id UUID NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    lesson INTEGER NOT NULL CHECK (lesson > 0),
    exercise_type VARCHAR(50) NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT fk_answers_exercise_user FOREIGN KEY (exercise_id, user_id) REFERENCES exercises(id, user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_answers_user_lesson ON answers(user_id, lesson);
CREATE INDEX IF NOT EXISTS idx_answers_exercise_created ON answers(exercise_id, created_at);

-- 6. MAGIC LINKS TABLE (Ephemeral authentication capability links)
CREATE TABLE IF NOT EXISTS magic_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token VARCHAR(64) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    lesson INTEGER NOT NULL CHECK (lesson > 0),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE NOT NULL,
    last_accessed_at TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_magic_links_token ON magic_links(token);
CREATE INDEX IF NOT EXISTS idx_magic_links_user_lesson ON magic_links(user_id, lesson);

-- 7. LESSON INGESTIONS (Idempotency ledger for incoming n8n raw text hashes)
CREATE TABLE IF NOT EXISTS lesson_ingestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_name VARCHAR(100) NOT NULL,
    text_hash VARCHAR(64) NOT NULL,
    lesson INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_lesson_ingestions_hash UNIQUE (user_id, course_name, text_hash)
);

CREATE INDEX IF NOT EXISTS idx_lesson_ingestions_hash ON lesson_ingestions(user_id, course_name, text_hash);

-- 8. USER SCHEDULES TABLE (Dispatches lesson emails via language_exercises_scheduler)
CREATE TABLE IF NOT EXISTS user_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    course_name VARCHAR(100) NOT NULL DEFAULT 'German Theory',
    lesson_id INTEGER NOT NULL CHECK (lesson_id > 0),
    when_to_send TIMESTAMPTZ NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'sent', 'failed', 'cancelled')),
    sent_at TIMESTAMPTZ DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_user_schedules_user_course_lesson UNIQUE (user_id, course_name, lesson_id)
);

CREATE INDEX IF NOT EXISTS idx_user_schedules_pending ON user_schedules(status, when_to_send);
CREATE INDEX IF NOT EXISTS idx_user_schedules_user_id ON user_schedules(user_id);
CREATE INDEX IF NOT EXISTS idx_user_schedules_email ON user_schedules(email);
