import logging
from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import JSONResponse

from app.core.security import verify_n8n_api_key
from app.schemas.api import IngestionResponse, WebhookIngestionPayload
from app.services.lesson_service import lesson_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["n8n Webhook Ingestion"])

@router.post(
    "/n8n/lessons",
    response_model=IngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest raw German lesson text from n8n",
    description="Receives raw email theory text from n8n, auto-provisions inactive users, assigns sequential lesson numbers, calls OpenRouter Gemini Flash to generate exercises, and issues a magic link."
)
async def ingest_n8n_lesson(
    payload: WebhookIngestionPayload,
    background_tasks: BackgroundTasks,
    run_async: bool = False,
    _: str = Depends(verify_n8n_api_key),
):
    if run_async:
        # Enqueue background execution so n8n is immediately unblocked with 202
        background_tasks.add_task(lesson_service.ingest_webhook_lesson, payload)
        return IngestionResponse(
            status="accepted",
            message=f"Lesson generation task accepted for {payload.email} and queued in background.",
        )
    else:
        # Synchronous execution
        result = await lesson_service.ingest_webhook_lesson(payload)
        return result
