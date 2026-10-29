from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_n8n_api_key(api_key: str = Security(api_key_header)) -> str:
    """Validate static X-API-Key header sent by n8n webhook."""
    if not api_key or api_key != settings.N8N_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
