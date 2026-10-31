# User Registration & Management Guide

[🏠 Home (README)](../README.md) • [🏗️ Architecture](architecture.md) • [📡 API Reference](api_reference.md) • [🤖 AI Engine](ai_engine.md) • [🗄️ Database](database_schema.md) • [⚙️ Configuration](configuration.md) • [👤 User Management](user_registration.md) • [⚡ Ingestion Webhook](exercises_webhook.md)

---

## 1. Zero-Auth User Architecture

The platform operates on a **Zero-Auth** model:
- Students do not have accounts with passwords or sign-in sessions.
- Students access their daily exercises and lessons directly via capability tokens:
  `http://localhost:5173/lesson/{token}` (Frontend) or `http://localhost:8000/api/lesson/{token}` (Backend).
- Legacy direct email routing is also supported for developer access:
  `http://localhost:5173/<email>/` or `http://localhost:8000/<email>/`.
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
   Visit: `http://localhost:8000/api/user/<email>/latest-lesson`
2. **Verify via Frontend:**
   Visit: `http://localhost:5173/<email>/`

---

## 7. Next Steps & Related Documentation

* [🏠 Back to README](../README.md)
* [🗄️ Database Schema](database_schema.md) — Table schemas and indexes.
* [⚡ Ingestion Webhook Guide](exercises_webhook.md) — How incoming payloads trigger provisioning.
* [📡 API Reference](api_reference.md) — User and lesson resolution endpoints.
