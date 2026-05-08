"""
Auralis Knowledge API
Endpoints for ingesting documents into the RAG knowledge base.
"""

from fastapi import APIRouter, HTTPException
from app.schemas.knowledge import IngestRequest, IngestResponse, KnowledgeStatus, FileIngestResult
from app.services.knowledge_service import knowledge_service
from app.core.logging import logger
import asyncio

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.post("/ingest", response_model=IngestResponse, summary="Ingest Documents")
async def ingest_documents(request: IngestRequest = None):
    """
    Ingest documents into the vector knowledge base.
    If no file_paths provided, ingests the default `knowledge_base/` directory.
    """
    try:
        loop = asyncio.get_event_loop()

        if request and request.file_paths:
            # Ingest specific files
            results_raw = []
            for path in request.file_paths:
                result = await loop.run_in_executor(None, knowledge_service.ingest_file, path)
                results_raw.append(result)
        else:
            # Default: ingest knowledge_base/ directory
            results_raw = await loop.run_in_executor(
                None, knowledge_service.ingest_directory, "./knowledge_base"
            )

        results = [FileIngestResult(**r) for r in results_raw]
        total_chunks = sum(r.chunks_created or 0 for r in results)

        return IngestResponse(
            success=True,
            files_processed=len(results),
            total_chunks_created=total_chunks,
            results=results,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("/status", response_model=KnowledgeStatus, summary="Knowledge Base Status")
async def get_knowledge_status():
    """Return the current state of the knowledge base (document count, collection info)."""
    try:
        status = knowledge_service.get_status()
        return KnowledgeStatus(**status)
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
