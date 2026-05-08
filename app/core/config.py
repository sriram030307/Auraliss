"""
Auralis Configuration Management
Loads settings from environment variables / .env file using Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "Auralis"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "AI-Powered Intelligent Interaction System"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── LLM Configuration ────────────────────────────────────────
    LLM_PROVIDER: str = "openai"  # "openai" or "ollama"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # ── Embedding Configuration ──────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── ChromaDB Configuration ───────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./chroma_data"
    CHROMA_COLLECTION_NAME: str = "auralis_knowledge"

    # ── RAG Configuration ────────────────────────────────────────
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K_RESULTS: int = 3

    # ── Conversation Configuration ───────────────────────────────
    MAX_CONVERSATION_TURNS: int = 20
    SYSTEM_PROMPT: str = (
        "You are Auralis, an advanced AI assistant powered by cutting-edge "
        "language models and retrieval-augmented generation. You are helpful, "
        "accurate, and provide detailed responses. When given context from "
        "a knowledge base, prioritize that information in your answers and "
        "cite your sources. Maintain a professional yet approachable tone."
    )

    # ── Frontend ─────────────────────────────────────────────────
    FRONTEND_DIR: str = "./frontend"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Singleton settings instance
settings = Settings()
