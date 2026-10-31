# API Reference

[🏠 Home (README)](../README.md) • [🏗️ Architecture](architecture.md) • [📡 API Reference](api_reference.md) • [🤖 AI Engine](ai_engine.md) • [🗄️ Database](database_schema.md) • [⚙️ Configuration](configuration.md) • [👤 User Management](user_registration.md) • [⚡ Ingestion Webhook](exercises_webhook.md)

---

## 1. Overview & Base URL

The API is served using FastAPI with automatic OpenAPI interactive documentation accessible at:
* **Interactive Swagger UI:** `http://localhost:8000/docs`
* **ReDoc UI:** `http://localhost:8000/redoc`
* **OpenAPI JSON Schema:** `http://localhost:8000/openapi.json`

### Authentication Schemes
| Endpoint Category | Auth Method | Header | Description |
| :--- | :--- | :--- | :--- |
| **Webhook Ingestion** | Static API Key | `X-API-Key: <N8N_API_KEY>` | Protects internal n8n ingestion pipeline |
| **Capability Lessons** | Ephemeral Token | URL Path: `/api/lesson/{token}` | Expiring token issued per lesson run |
| **Written Evaluation** | Token or Open | Request body: `token` / `exercise_id` | Validates session or bound exercise context |
| **Public / System** | None | — | Health checks, documentation, root info |

---

## 2. Webhook Ingestion

### `POST /api/webhooks/n8n/lessons`
Ingests raw German theory email text from n8n, triggers lesson and exercise generation, assigns sequential lesson numbers, and issues an ephemeral capability magic link.

#### Headers
```http
Content-Type: application/json
X-API-Key: your-n8n-internal-secret-key
```

#### Query Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `run_async` | `boolean` | No | `false` | When `true`, delegates lesson generation to FastAPI `BackgroundTasks` and returns immediately. |

#### Request Body
```json
{
  "email": "luismaiasombra@gmail.com",
  "course_name": "German Theory",
  "date": "2026-10-30",
  "raw_text": "Heute lernen wir Wechselpräpositionen: an, auf, hinter, in, neben, über, unter, vor, zwischen..."
}
```

#### Responses

##### `202 Accepted` - Lesson Successfully Generated
```json
{
  "status": "processed",
  "message": "Lesson 12 successfully generated with 4 exercises.",
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "lesson": 12,
  "magic_link_token": "aZ89_-dKl91qW0...",
  "magic_link_url": "http://localhost:5173/lesson/aZ89_-dKl91qW0...",
  "exercise_count": 4
}
```

##### `202 Accepted` - User Inactive / Auto-Provisioned
```json
{
  "status": "skipped_inactive",
  "message": "User was newly auto-provisioned as inactive. Lesson generation skipped until user is activated.",
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "lesson": null,
  "magic_link_token": null,
  "magic_link_url": null,
  "exercise_count": null
}
```

##### `202 Accepted` - Duplicate Raw Text
```json
{
  "status": "duplicate",
  "message": "Duplicate raw text already ingested for this user and course.",
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "lesson": 12,
  "magic_link_token": null,
  "magic_link_url": null,
  "exercise_count": null
}
```

##### `401 Unauthorized`
Returned if the `X-API-Key` header is missing or does not match `N8N_API_KEY`.

---

## 3. Lesson Resolution

### `GET /api/lesson/{token}`
Resolves an ephemeral capability magic link token, verifying that the token is unexpired, unrevoked, and the user is active. Returns all exercises and the theory summary bound to that lesson.

#### Path Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `token` | `string` | Yes | 64-character URL-safe capability token |

#### Responses

##### `200 OK`
```json
{
  "is_valid": true,
  "status": "active",
  "expires_at": "2026-11-06T14:00:00Z",
  "lesson_exercises": [
    {
      "id": "c1f7a184-7a43-4e2b-a012-1f4a9b5c3d2e",
      "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "subscription_id": "f5a2b1c4-1234-5678-9abc-def012345678",
      "date": "2026-10-30",
      "lesson": 12,
      "exercise_type": "multiple_choice",
      "question": "Wählen Sie die richtige Form: 'Ich stelle das Buch auf _____ Tisch.'",
      "options": [
        {
          "text": "den",
          "is_correct": true,
          "explanation": "Richtig! 'Stellen' indicates movement/direction (Wohin? Akkusativ maskulin: der -> den)."
        },
        {
          "text": "dem",
          "is_correct": false,
          "explanation": "Falsch. 'Dem' ist Dativ. Dativ wird für eine feste Position (Wo?) verwendet."
        }
      ],
      "theory_summary": "In today's lesson, we examine two-way prepositions (Wechselpräpositionen)...",
      "created_at": "2026-10-30T14:05:00Z"
    },
    {
      "id": "e2f8b295-8b54-4f3c-b123-2e5b0c6d4e3f",
      "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "subscription_id": "f5a2b1c4-1234-5678-9abc-def012345678",
      "date": "2026-10-30",
      "lesson": 12,
      "exercise_type": "written",
      "question": "Bilden Sie einen Satz mit 'legen' und 'der Tisch' (Wohin?).",
      "options": null,
      "theory_summary": "In today's lesson, we examine two-way prepositions (Wechselpräpositionen)...",
      "created_at": "2026-10-30T14:05:00Z"
    }
  ]
}
```

##### `410 Gone` - Token Expired
```json
{
  "detail": "Session Expired. This magic link has exceeded its validity window."
}
```

##### `404 Not Found` - Invalid or Revoked Token
```json
{
  "detail": "Magic link not_found."
}
```

##### `403 Forbidden` - User Inactive
```json
{
  "detail": "User account is inactive."
}
```

---

### `GET /api/user/{email}/latest-lesson`
Zero-Auth lookup returning the latest sequential lesson exercises for an active, subscribed student.

#### Path & Query Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `email` | `string` | Yes | — | Student's unique email address |
| `course` | `string` | No | `German Theory` | Course name filter |

#### Responses
##### `200 OK`
```json
{
  "email": "luismaiasombra@gmail.com",
  "is_active": true,
  "is_subscribed": true,
  "lesson": 12,
  "course_name": "German Theory",
  "exercises": [ ... ]
}
```

##### `403 Forbidden`
Returned if `is_active` is `false` or user is unsubscribed.

---

## 4. Exercise Evaluation & Answers

### `POST /api/exercises/evaluate-written`
Performs dynamic, real-time AI evaluation of a student's German written answer using OpenRouter (`google/gemini-2.5-flash`), evaluating syntax, case endings, and lexical choice in the context of the lesson.

#### Request Body
```json
{
  "token": "aZ89_-dKl91qW0...",
  "exercise_id": "e2f8b295-8b54-4f3c-b123-2e5b0c6d4e3f",
  "question_prompt": "Bilden Sie einen Satz mit 'legen' und 'der Tisch' (Wohin?).",
  "user_answer": "Ich lege das Buch auf den Tisch."
}
```
*Note: Either `token` or `exercise_id` can be provided for contextual lookup.*

#### Responses

##### `200 OK` - Valid Response
```json
{
  "is_correct": true,
  "explanation": "Ausgezeichnet! You correctly used 'legen' which demands Akkusativ ('den Tisch') because it indicates movement towards a destination."
}
```

##### `200 OK` - Invalid Response
```json
{
  "is_correct": false,
  "explanation": "Nicht ganz richtig. 'Legen' requires the Akkusativ case for two-way prepositions (Wohin?), but you used the Dativ form 'dem'. Correct sentence: 'Ich lege das Buch auf den Tisch.'"
}
```

##### `410 Gone`
Returned if the provided `token` has expired or been revoked.

---

### `POST /api/answers/record`
Persists a student's answer (for either multiple choice or written exercises) into the `answers` table.

#### Request Body
```json
{
  "exercise_id": "c1f7a184-7a43-4e2b-a012-1f4a9b5c3d2e",
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "answer": "den",
  "date": "2026-10-30"
}
```

#### Responses
##### `200 OK`
```json
{
  "success": true,
  "answer_id": "7d9b4c2a-9f1e-4a6c-b3a1-5d8e7f9a0b1c",
  "message": "Answer recorded successfully."
}
```

---

## 5. System & Health Endpoints

### `GET /health`
Returns system status, active configuration versions, and AI model identifier.

#### Response `200 OK`
```json
{
  "status": "healthy",
  "app": "German Exercise Platform",
  "version": "1.0.0",
  "environment": "development",
  "ai_model": "google/gemini-2.5-flash"
}
```

### `GET /`
Welcome banner with discovery links to `/docs` and `/health`.

---

## 6. Next Steps & Related Documentation

* [🏗️ System Architecture](architecture.md) — Architectural patterns, security model, and sequence flows.
* [🤖 AI Engine Guide](ai_engine.md) — How OpenRouter generates exercises and evaluates written answers.
* [🗄️ Database Schema](database_schema.md) — Table definitions and relationships.
* [⚙️ Configuration Guide](configuration.md) — Settings and environment variables.
