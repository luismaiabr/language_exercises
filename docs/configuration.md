# Configuration & Environment Guide

[🏠 Home (README)](../README.md) • [🏗️ Architecture](architecture.md) • [📡 API Reference](api_reference.md) • [🤖 AI Engine](ai_engine.md) • [🗄️ Database](database_schema.md) • [⚙️ Configuration](configuration.md) • [👤 User Management](user_registration.md) • [⚡ Ingestion Webhook](exercises_webhook.md)

---

## 1. Architectural Philosophy

In this platform, **secrets** and **application parameters** are strictly segregated:
* **Secrets belong in `.env`:** API keys, database credentials, sensitive webhook secrets.
* **Operational parameters belong in `config/*.yaml`:** Model selection, prompt templates, timeouts, retry counts, server ports, CORS origins, and capability token expiration policies.

This design enables changing prompts or tuning AI parameters without touching server environment variables or risking credential exposure in Git.

---

## 2. Secrets & `.env` Setup

Copy the example file to `.env`:
```powershell
cp .env.example .env
```

### Environment Variables Matrix

| Variable | Required | Description | Example / Default |
| :--- | :--- | :--- | :--- |
| `SUPABASE_URL` | **Yes** | Your Supabase Project API URL | `https://xyzcompany.supabase.co` |
| `SUPABASE_KEY` | **Yes** | Supabase service_role or anon key | `eyJhbGciOiJIUzI1NiIsInR5cCI6...` |
| `OPENROUTER_API_KEY` | **Yes** | OpenRouter bearer API key | `sk-or-v1-abcdef123456...` |
| `N8N_API_KEY` | **Yes** | Secret static token sent by n8n | `n8n-internal-secret-token` |
| `CONFIG_DIR` | No | Path to YAML config directory | Defaults to `./config` |

> [!NOTE]
> If `OPENROUTER_API_KEY` is not provided (or set to placeholder values), the backend automatically activates a local mock generator so development and automated tests can run without an external connection.

---

## 3. Dedicated YAML Configurations (`config/`)

### 3.1. `config/app.yaml` — Server & Application Rules
Configures runtime behavior, server ports, CORS access, and capability token lifespan:

```yaml
app:
  name: "German Exercise Platform"
  version: "1.0.0"
  description: "AI-driven German language exercise generation & evaluation platform"
  environment: "development"

server:
  host: "0.0.0.0"
  port: 8000
  reload: true
  cors_origins:
    - "http://localhost:5173"
    - "http://localhost:3000"
    - "http://127.0.0.1:5173"
    - "http://127.0.0.1:3000"
  timeout_seconds: 30

magic_links:
  timespan_days: 7                           # Validity window for capability URLs
  base_url: "http://localhost:5173/lesson"   # Base URL delivered to students

courses:
  default_course_name: "German Theory"
  auto_provision_inactive: true              # Auto-creates unregistered students as inactive
  allowed_exercise_types:
    - "multiple_choice"
    - "written"
```

### 3.2. `config/ai.yaml` — OpenRouter & AI Parameters
Governs model selection, network timeouts, temperature settings, and max token limits:

```yaml
openrouter:
  base_url: "https://openrouter.ai/api/v1"
  model: "google/gemini-2.5-flash"
  timeout_seconds: 45
  max_retries: 3
  site_url: "https://german-exercises.local"
  site_name: "German AI Exercises"

generation:
  temperature: 0.2    # Low temperature to prevent hallucinations in German grammar
  max_tokens: 3500    # Accommodates rich options with per-choice explanations

evaluation:
  temperature: 0.1    # Deterministic grammar evaluation
  max_tokens: 800
```

### 3.3. `config/prompts.yaml` — System & Template Prompts
Contains version-controlled prompt templates for:
* **`lesson_generation`:** Instructions for extracting `theory_summary`, building valid `multiple_choice` options with exhaustive explanations, and formulating `written` prompts.
* **`written_evaluation`:** Instructions for evaluating student written answers, diagnosing grammatical errors, and providing encouraging feedback in English.

---

## 4. How Settings are Loaded in Code

The configuration loader lives in `app.core.config.Settings`. It:
1. Inherits from `pydantic_settings.BaseSettings`.
2. Loads `.env` automatically into environment variables.
3. Parses `app.yaml`, `ai.yaml`, and `prompts.yaml` on application startup.
4. Exposes typed properties throughout the codebase via `from app.core.config import settings`.

---

## 5. Next Steps & Related Documentation

* [🏗️ System Architecture](architecture.md) — System components and data flow.
* [📡 API Reference](api_reference.md) — HTTP API endpoints and authentication.
* [🤖 AI Engine Guide](ai_engine.md) — AI model parameters and prompts.
* [⚡ Ingestion Webhook Guide](exercises_webhook.md) — Configuring webhook authentication and payload format.
