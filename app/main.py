import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import answers, exercises, lessons, webhooks
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("language_exercises")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.prompts.get("description", "AI-Driven German Exercise Platform Backend"),
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(webhooks.router, prefix="/api")
app.include_router(lessons.router)
app.include_router(exercises.router)
app.include_router(answers.router)

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_environment,
        "ai_model": settings.openrouter_model,
    }

@app.get("/", tags=["System"])
async def root():
    return {
        "message": f"Welcome to {settings.app_name} API",
        "docs": "/docs",
        "health": "/health",
    }

# Zero-Auth route compatibility: GET /{email}/
@app.get("/{email}/", tags=["Legacy Route Compatibility"])
async def get_user_route(email: str):
    from app.services.lesson_service import lesson_service
    return lesson_service.resolve_user_latest_lesson(email=email)
