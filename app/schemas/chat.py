"""
Auralis Chat Pydantic Schemas
Request/response models for the chat API endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ChatRequest(BaseModel):
    """Request model for sending a chat message."""
    message: str = Field(..., min_length=1, max_length=4000, description="User's message")
    session_id: Optional[str] = Field(None, description="Existing session ID (creates new if omitted)")
    use_rag: bool = Field(True, description="Whether to use RAG knowledge retrieval")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="LLM temperature")

    model_config = {"json_schema_extra": {"example": {
        "message": "What is Retrieval-Augmented Generation?",
        "session_id": None,
        "use_rag": True,
        "temperature": 0.7,
    }}}


class SourceDocument(BaseModel):
    """A retrieved source document from the knowledge base."""
    content: str
    source: str
    chunk_index: int
    similarity: float


class ChatResponse(BaseModel):
    """Response model for a chat message."""
    response: str
    session_id: str
    is_new_session: bool
    sources: List[SourceDocument] = Field(default_factory=list)
    rag_used: bool
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SessionResponse(BaseModel):
    """Response model for session creation."""
    session_id: str
    created_at: str
    title: str


class SessionSummary(BaseModel):
    """Summary of a single conversation session."""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ConversationMessage(BaseModel):
    """A single message in a conversation."""
    role: str
    content: str
    timestamp: str


class ConversationHistoryResponse(BaseModel):
    """Full conversation history for a session."""
    session_id: str
    title: str
    messages: List[ConversationMessage]
    message_count: int


class SessionListResponse(BaseModel):
    """List of all active sessions."""
    sessions: List[SessionSummary]
    total: int


class DeleteSessionResponse(BaseModel):
    """Response for session deletion."""
    success: bool
    session_id: str
    message: str
