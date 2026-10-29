# AI-Driven German Exercise Platform - Backend

FastAPI backend for ingesting raw German theory emails from n8n, generating interactive exercises using OpenRouter (Gemini Flash), persisting to Supabase PostgreSQL, and managing capability-based magic links.

## Tech Stack
- **Framework**: FastAPI (Python 3.11+) with Pydantic V2
- **Dependency Management**: Poetry
- **Database**: Supabase (PostgreSQL)
- **AI Model**: OpenRouter API (`google/gemini-2.5-flash`)
- **Transport**: Ingestion webhook for n8n (`POST /api/webhooks/n8n/lessons`)

## Configuration Structure
Per system requirements, settings are cleanly separated across dedicated configuration files rather than thrown into `.env`:

```
config/
├── app.yaml      # Server host/port, CORS origins, magic link timespan, courses
├── ai.yaml       # OpenRouter model, temperatures, max tokens, retries
└── prompts.yaml  # System and user prompt templates for generation & evaluation
```

### Environment Secrets (`.env`)
Only sensitive credentials and secrets belong in `.env`:
```ini
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-or-anon-key
OPENROUTER_API_KEY=sk-or-v1-your-openrouter-key
N8N_API_KEY=your-internal-n8n-secret-api-key
```

## Database Setup
Run the SQL schema located in [`sql/schema.sql`](file:///c:/Users/Luis%20Maia/Documents/MY%20APPS/EDUCATION/language_exercises/sql/schema.sql) in your Supabase SQL Editor. It sets up:
1. `users` - Unique email indexing, active status
2. `subscriptions` - Course subscriptions per user
3. `exercises` - Sequential lesson exercises with JSONB options
4. `answers` - Answers with composite foreign key ownership
5. `magic_links` - Ephemeral capability tokens with configurable expiration
6. `lesson_ingestions` - Idempotency text-hash ledger

## Running the Backend
```powershell
# Install dependencies
python -m poetry install

# Run development server
python -m poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Interactive API docs are available at `http://localhost:8000/docs`.

## Running Backend Tests
```powershell
python -m poetry run python tests/test_backend.py
```