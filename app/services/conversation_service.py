"""
Auralis Conversation Service
Multi-turn conversation context management with sliding window memory.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from app.core.config import settings
from app.core.logging import logger


class ConversationSession:
    """Represents a single user's conversation session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.messages: List[Dict[str, str]] = []
        self.title: str = "New Conversation"

    def add_message(self, role: str, content: str):
        """Add a message to the conversation history."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.updated_at = datetime.utcnow()
        # Auto-title from first user message
        if role == "user" and self.title == "New Conversation":
            self.title = content[:60] + ("..." if len(content) > 60 else "")

    def get_context_window(self) -> List[Dict[str, str]]:
        """
        Return the conversation history formatted for LLM input.
        Uses a sliding window of the last MAX_CONVERSATION_TURNS turns.
        Includes the system prompt as the first message.
        """
        # Start with system prompt
        context = [{"role": "system", "content": settings.SYSTEM_PROMPT}]

        # Apply sliding window to user/assistant messages only
        recent = self.messages[-settings.MAX_CONVERSATION_TURNS:]
        for msg in recent:
            context.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        return context

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": len(self.messages),
            "messages": self.messages,
        }


class ConversationService:
    """
    In-memory conversation store.
    Manages creation, retrieval, and deletion of conversation sessions.
    """

    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}
        logger.info("Conversation Service initialized")

    def create_session(self) -> ConversationSession:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())
        session = ConversationSession(session_id)
        self._sessions[session_id] = session
        logger.info(f"Session created: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Retrieve an existing session by ID."""
        return self._sessions.get(session_id)

    def get_or_create_session(self, session_id: Optional[str]) -> Tuple[ConversationSession, bool]:
        """
        Return existing session or create a new one.
        Returns (session, is_new) tuple.
        """
        if session_id and session_id in self._sessions:
            return self._sessions[session_id], False
        return self.create_session(), True

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if deleted, False if not found."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Session deleted: {session_id}")
            return True
        return False

    def list_sessions(self) -> List[dict]:
        """Return a summary list of all active sessions."""
        return [
            {
                "session_id": s.session_id,
                "title": s.title,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": len(s.messages),
            }
            for s in sorted(
                self._sessions.values(),
                key=lambda x: x.updated_at,
                reverse=True,
            )
        ]

    def add_exchange(
        self,
        session: ConversationSession,
        user_message: str,
        assistant_message: str,
    ):
        """Add a user + assistant message pair to the session."""
        session.add_message("user", user_message)
        session.add_message("assistant", assistant_message)

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)


# Singleton instance
conversation_service = ConversationService()
