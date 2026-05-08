"""
Auralis Chat API
Core chat endpoints: send messages, manage sessions, retrieve history.
"""

from fastapi import APIRouter, HTTPException
from app.schemas.chat import (
    ChatRequest, ChatResponse, SourceDocument,
    SessionResponse, SessionListResponse, SessionSummary,
    ConversationHistoryResponse, ConversationMessage,
    DeleteSessionResponse,
)
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service
from app.services.conversation_service import conversation_service
from app.core.logging import logger

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, summary="Send a Message")
async def send_message(request: ChatRequest):
    """
    Send a message and receive a context-aware AI response.
    Optionally uses RAG to augment the prompt with knowledge base context.
    Creates a new session if no session_id is provided.
    """
    try:
        # Get or create conversation session
        session, is_new = conversation_service.get_or_create_session(request.session_id)

        # Get the LLM service
        llm = llm_service()

        # RAG pipeline: retrieve and augment
        sources = []
        user_content = request.message
        rag_used = False

        if request.use_rag:
            augmented_content, raw_sources = await rag_service.retrieve_and_augment(request.message)
            if raw_sources:
                user_content = augmented_content
                sources = [SourceDocument(**s) for s in raw_sources]
                rag_used = True
                logger.info(f"RAG enriched query with {len(sources)} sources")

        # Build context window (system prompt + conversation history + new query)
        messages = session.get_context_window()
        messages.append({"role": "user", "content": user_content})

        # Generate response
        response_text = await llm.generate(
            messages=messages,
            temperature=request.temperature,
        )

        # Save the exchange (use original message for history readability)
        conversation_service.add_exchange(session, request.message, response_text)

        logger.info(
            f"Chat response | Session: {session.session_id[:8]}... | "
            f"RAG: {rag_used} | Sources: {len(sources)}"
        )

        return ChatResponse(
            response=response_text,
            session_id=session.session_id,
            is_new_session=is_new,
            sources=sources,
            rag_used=rag_used,
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.post("/session", response_model=SessionResponse, summary="Create New Session")
async def create_session():
    """Create a new conversation session and return its ID."""
    session = conversation_service.create_session()
    return SessionResponse(
        session_id=session.session_id,
        created_at=session.created_at.isoformat(),
        title=session.title,
    )


@router.get("/sessions", response_model=SessionListResponse, summary="List All Sessions")
async def list_sessions():
    """Return a summary of all active conversation sessions."""
    sessions = conversation_service.list_sessions()
    return SessionListResponse(
        sessions=[SessionSummary(**s) for s in sessions],
        total=len(sessions),
    )


@router.get("/{session_id}/history", response_model=ConversationHistoryResponse, summary="Get Conversation History")
async def get_history(session_id: str):
    """Retrieve the full message history for a conversation session."""
    session = conversation_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    data = session.to_dict()
    return ConversationHistoryResponse(
        session_id=data["session_id"],
        title=data["title"],
        messages=[ConversationMessage(**m) for m in data["messages"]],
        message_count=data["message_count"],
    )


@router.delete("/session/{session_id}", response_model=DeleteSessionResponse, summary="Delete Session")
async def delete_session(session_id: str):
    """Delete a conversation session and all its history."""
    deleted = conversation_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return DeleteSessionResponse(
        success=True,
        session_id=session_id,
        message="Session deleted successfully",
    )
