"""
Auralis Knowledge Pydantic Schemas
Request/response models for knowledge ingestion endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class IngestRequest(BaseModel):
    """Request to ingest files from specified paths."""
    file_paths: Optional[List[str]] = Field(
        None,
        description="List of file paths to ingest. If omitted, ingests the default knowledge_base/ directory.",
    )

    model_config = {"json_schema_extra": {"example": {
        "file_paths": ["./knowledge_base/sample_ai_overview.txt"]
    }}}


class FileIngestResult(BaseModel):
    """Result for a single file ingestion."""
    file: str
    chunks_created: Optional[int] = 0
    characters: Optional[int] = None
    error: Optional[str] = None


class IngestResponse(BaseModel):
    """Response for a knowledge ingestion request."""
    success: bool
    files_processed: int
    total_chunks_created: int
    results: List[FileIngestResult]


class KnowledgeStatus(BaseModel):
    """Current state of the knowledge base."""
    status: str
    collection_name: str
    total_chunks: int
    persist_directory: str
