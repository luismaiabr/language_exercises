# User Registration & Management Guide

This document explains how users and course subscriptions are registered and managed in the AI-Driven German Exercise Platform.

---

## 1. Zero-Auth User Architecture

The platform operates on a **Zero-Auth** model:
- Students do not have accounts with passwords or sign-in sessions.
- Students access their daily exercises and lessons directly via their personalized URL:
  `http://localhost:5173/<email>/` (Frontend) or `http://localhost:8000/<email>/` (Backend).
- For a student to receive AI-generated lessons, two conditions must be met:
  1. The user must exist in the `users` table with `is_active = TRUE`.
  2. The user must have a record in `subscriptions` for the course (e.g., `course_name = 'German Theory'`) with `is_subscribed = TRUE`.

---

## 2. Manual User Registration (SQL)

To manually register and activate a user, run the following SQL script in the **Supabase SQL Editor** (or connected PostgreSQL client):

### Example: Registering 'Luis'

```sql
-- 1. Insert User (Luis)
INSERT INTO users (email, name, is_active)
VALUES ('luismaiasombra@gmail.com', 'Luis', TRUE)
ON CONFLICT (email) DO UPDATE SET is_active = TRUE;

-- 2. Create / Activate Course Subscription
INSERT INTO subscriptions (user_id, course_name, is_subscribed)
SELECT id, 'German Theory', TRUE
FROM users
WHERE email = 'luismaiasombra@gmail.com'
ON CONFLICT (user_id, course_name) DO UPDATE SET is_subscribed = TRUE;
```

---

## 3. Template for Adding Any New Student

Replace `<student_email>`, `<student_name>`, and `<course_name>` as needed:

```sql
-- 1. Insert or activate student
INSERT INTO users (email, name, is_active)
VALUES ('<student_email>', '<student_name>', TRUE)
ON CONFLICT (email) DO UPDATE SET is_active = TRUE;

-- 2. Ensure course subscription is active
INSERT INTO subscriptions (user_id, course_name, is_subscribed)
SELECT id, '<course_name>', TRUE
FROM users
WHERE email = '<student_email>'
ON CONFLICT (user_id, course_name) DO UPDATE SET is_subscribed = TRUE;
```

---

## 4. Automated User Provisioning (via n8n Webhook)

When an incoming email lesson is ingested via the webhook (`POST /api/webhooks/n8n/lessons`):

1. **New Users (Inactive by Default):**
   If an incoming lesson email has an address not yet present in `users`, the backend **auto-provisions** the user and matching course subscription with `is_active = FALSE`.
   - Lesson generation is skipped to avoid unauthorized AI token usage.
2. **Activating Auto-Provisioned Users:**
   To approve an auto-provisioned user so they can begin receiving generated lessons on future emails:
   ```sql
   UPDATE users
   SET is_active = TRUE
   WHERE email = 'student@example.com';
   ```

---

## 5. Deactivating or Unsubscribing a User

- **Temporarily pause a student's lessons:**
  ```sql
  UPDATE users
  SET is_active = FALSE
  WHERE email = 'student@example.com';
  ```
- **Unsubscribe from a specific course only:**
  ```sql
  UPDATE subscriptions s
  SET is_subscribed = FALSE
  FROM users u
  WHERE s.user_id = u.id
    AND u.email = 'student@example.com'
    AND s.course_name = 'German Theory';
  ```

---

## 6. Verifying Registration

After running the registration script:

1. **Verify via Backend API:**
   Visit: `http://localhost:8000/<email>/` (e.g. `http://localhost:8000/luismaiasombra@gmail.com/`)
2. **Verify via Frontend:**
   Visit: `http://localhost:5173/<email>/` (e.g. `http://localhost:5173/luismaiasombra@gmail.com/`)
