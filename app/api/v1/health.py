"""
Auralis Health Check API
Simple endpoint to verify the system is running and report component status.
"""

from fastapi import APIRouter
from datetime import datetime
from app.core.config import settings
from app.db.vector_store import vector_store
from app.services.llm_service import llm_service

router = APIRouter(tags=["Health"])


@router.get("/health", summary="System Health Check")
async def health_check():
    """
    Returns the current health status of all Auralis components.
    """
    kb_stats = vector_store.get_stats()
    llm = llm_service()

    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "llm": {
                "provider": settings.LLM_PROVIDER,
                "model": settings.OPENAI_MODEL if settings.LLM_PROVIDER == "openai" else settings.OLLAMA_MODEL,
                "available": llm.is_available(),
            },
            "vector_store": {
                "status": "ready",
                "total_chunks": kb_stats["total_documents"],
                "collection": kb_stats["collection_name"],
            },
        },
    }
